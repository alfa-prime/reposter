"""Проверка учётных данных и защита входа от автоматического перебора."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.client_metadata import (
    normalize_client_ip,
    normalize_request_id,
)
from news_reposter.auth.identity import IdentityValidationError, prepare_username
from news_reposter.auth.login_security import (
    ip_lock_key,
    username_fingerprint,
    username_lock_key,
)
from news_reposter.auth.passwords import MAX_PASSWORD_LENGTH, PasswordManager
from news_reposter.config import Settings, get_settings
from news_reposter.db.models import LoginAttempt, User
from news_reposter.repositories.login_attempt import LoginAttemptRepository
from news_reposter.repositories.user import UserRepository
from news_reposter.services.user_sessions import (
    CreatedSession,
    SessionUserUnavailableError,
    UserSessionService,
)


class InvalidCredentialsError(RuntimeError):
    """Логин и пароль не соответствуют активной учётной записи."""


class LoginRateLimitedError(RuntimeError):
    """Новая проверка пароля временно запрещена."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Слишком много попыток входа")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Пользователь и однократно возвращаемые секреты новой сессии."""

    user: User
    created_session: CreatedSession = field(repr=False)


class AuthenticationService:
    """Аутентифицирует пользователя и атомарно создаёт серверную сессию."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        password_manager: PasswordManager | None = None,
        user_repository: UserRepository | None = None,
        attempt_repository: LoginAttemptRepository | None = None,
        session_service: UserSessionService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.passwords = password_manager or PasswordManager()
        self.users = user_repository or UserRepository(session)
        self.attempts = attempt_repository or LoginAttemptRepository(session)
        self.user_sessions = session_service or UserSessionService(
            session,
            settings=self.settings,
        )

    async def authenticate(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> AuthenticationResult:
        """Проверяет пароль, пишет аудит и создаёт сессию при успехе."""

        current_time = _utc_time(now)
        fingerprint = username_fingerprint(username)
        normalized_ip = normalize_client_ip(client_ip)

        lock_keys = [username_lock_key(fingerprint)]
        if normalized_ip is not None:
            lock_keys.append(ip_lock_key(normalized_ip))
        await self.attempts.acquire_rate_limit_locks(lock_keys)

        retry_after = await self._retry_after(
            fingerprint=fingerprint,
            client_ip=normalized_ip,
            now=current_time,
        )
        if retry_after is not None:
            await self.session.rollback()
            raise LoginRateLimitedError(retry_after)

        user = await self._find_user(username)
        verified, updated_hash = self._verify_password(password, user)
        is_successful = verified and user is not None and user.is_active

        attempt = LoginAttempt(
            username_fingerprint=fingerprint,
            user_id=user.user_id if user is not None else None,
            ip_address=normalized_ip,
            was_successful=is_successful,
            attempted_at=current_time,
            request_id=normalize_request_id(request_id),
        )
        self.attempts.add(attempt)

        if not is_successful or user is None:
            await self._commit()
            raise InvalidCredentialsError("Неверный логин или пароль")

        if updated_hash is not None:
            user.password_hash = updated_hash
        user.last_login_at = current_time

        try:
            created_session = await self.user_sessions.create_for_locked_user(
                user,
                client_ip=normalized_ip,
                user_agent=user_agent,
                now=current_time,
            )
        except SessionUserUnavailableError as exc:
            raise InvalidCredentialsError("Неверный логин или пароль") from exc

        return AuthenticationResult(user=user, created_session=created_session)

    async def _find_user(self, username: str) -> User | None:
        try:
            normalized = prepare_username(username).normalized
        except IdentityValidationError:
            return None
        return await self.users.get_by_normalized_username_for_update(normalized)

    def _verify_password(
        self,
        password: str,
        user: User | None,
    ) -> tuple[bool, str | None]:
        if not 1 <= len(password) <= MAX_PASSWORD_LENGTH:
            self.passwords.verify_dummy(password[:MAX_PASSWORD_LENGTH])
            return False, None
        if user is None:
            self.passwords.verify_dummy(password)
            return False, None
        return self.passwords.verify_and_update(password, user.password_hash)

    async def _retry_after(
        self,
        *,
        fingerprint: bytes,
        client_ip: str | None,
        now: datetime,
    ) -> int | None:
        username_failures = await self.attempts.recent_failed_by_username(
            fingerprint,
            limit=self.settings.auth_login_max_attempts_per_username,
        )
        retry_after = _retry_after_seconds(
            username_failures,
            threshold=self.settings.auth_login_max_attempts_per_username,
            now=now,
            attempt_window=self._attempt_window,
            block_duration=self._block_duration,
        )

        if client_ip is None:
            return retry_after

        ip_failures = await self.attempts.recent_failed_by_ip(
            client_ip,
            limit=self.settings.auth_login_max_attempts_per_ip,
        )
        ip_retry_after = _retry_after_seconds(
            ip_failures,
            threshold=self.settings.auth_login_max_attempts_per_ip,
            now=now,
            attempt_window=self._attempt_window,
            block_duration=self._block_duration,
        )
        if retry_after is None:
            return ip_retry_after
        if ip_retry_after is None:
            return retry_after
        return max(retry_after, ip_retry_after)

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @property
    def _attempt_window(self) -> timedelta:
        return timedelta(minutes=self.settings.auth_login_attempt_window_minutes)

    @property
    def _block_duration(self) -> timedelta:
        return timedelta(minutes=self.settings.auth_login_block_minutes)


def _retry_after_seconds(
    failure_times: list[datetime],
    *,
    threshold: int,
    now: datetime,
    attempt_window: timedelta,
    block_duration: timedelta,
) -> int | None:
    if len(failure_times) < threshold:
        return None

    recent = sorted(failure_times[:threshold], reverse=True)
    newest = recent[0]
    oldest = recent[-1]
    if newest - oldest > attempt_window:
        return None

    remaining = newest + block_duration - now
    if remaining <= timedelta(0):
        return None
    return max(1, int(remaining.total_seconds() + 0.999))


def _utc_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Время попытки входа должно содержать часовой пояс")
    return value.astimezone(UTC)
