"""Правила создания, проверки и отзыва серверных сессий."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.client_metadata import (
    normalize_client_ip,
    normalize_user_agent,
)
from news_reposter.auth.session_tokens import (
    SessionTokens,
    generate_session_tokens,
    hash_token,
)
from news_reposter.config import Settings, get_settings
from news_reposter.db.models import User, UserSession
from news_reposter.repositories.user_session import UserSessionRepository


class SessionRevocationReason(StrEnum):
    """Стабильные технические причины отзыва серверной сессии."""

    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    SESSION_LIMIT = "session_limit"
    IDLE_TIMEOUT = "idle_timeout"
    ABSOLUTE_TIMEOUT = "absolute_timeout"
    USER_INACTIVE = "user_inactive"
    PASSWORD_CHANGED = "password_changed"
    ADMIN_REVOKED = "admin_revoked"


class InvalidSessionError(RuntimeError):
    """Сессия отсутствует или больше не даёт доступ к приложению."""


class SessionUserUnavailableError(RuntimeError):
    """Для указанного пользователя нельзя создать новую сессию."""


@dataclass(frozen=True, slots=True)
class CreatedSession:
    """Новая запись и однократно возвращаемые клиентские секреты."""

    session: UserSession
    tokens: SessionTokens = field(repr=False)


class UserSessionService:
    """Поддерживает серверную политику жизненного цикла сессий."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        repository: UserSessionRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.sessions = repository or UserSessionRepository(session)

    async def create(
        self,
        user_id: int,
        *,
        client_ip: str | None = None,
        user_agent: str | None = None,
        now: datetime | None = None,
    ) -> CreatedSession:
        """Создаёт сессию и отзывает самые старые сверх лимита."""

        current_time = _utc_time(now)
        user = await self.sessions.lock_user(user_id)
        return await self.create_for_locked_user(
            user,
            client_ip=client_ip,
            user_agent=user_agent,
            now=current_time,
        )

    async def create_for_locked_user(
        self,
        user: User | None,
        *,
        client_ip: str | None = None,
        user_agent: str | None = None,
        now: datetime | None = None,
    ) -> CreatedSession:
        """Создаёт сессию для уже заблокированной строки пользователя."""

        current_time = _utc_time(now)
        if user is None or not user.is_active:
            await self.session.rollback()
            raise SessionUserUnavailableError(
                "Пользователь не найден или его учётная запись отключена"
            )

        user_id = user.user_id
        idle_cutoff = current_time - self._idle_lifetime
        usable_sessions = await self.sessions.list_usable_for_user(
            user_id,
            now=current_time,
            idle_cutoff=idle_cutoff,
        )
        excess_count = (
            len(usable_sessions) - self.settings.auth_max_sessions_per_user + 1
        )
        for old_session in usable_sessions[: max(0, excess_count)]:
            await self.sessions.revoke_session(
                old_session.session_id,
                revoked_at=current_time,
                reason=SessionRevocationReason.SESSION_LIMIT.value,
            )

        created = self._prepare_session(
            user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            now=current_time,
        )

        await self._commit()
        await self.session.refresh(created.session)
        return created

    async def replace_after_password_change(
        self,
        user: User | None,
        *,
        client_ip: str | None = None,
        user_agent: str | None = None,
        now: datetime | None = None,
    ) -> CreatedSession:
        """Отзывает прежние сессии и атомарно выдаёт одну новую.

        Строка пользователя должна быть заранее заблокирована вызывающим
        сервисом. Commit включает и уже внесённое изменение пароля.
        """

        current_time = _utc_time(now)
        if user is None or not user.is_active:
            await self.session.rollback()
            raise SessionUserUnavailableError(
                "Пользователь не найден или его учётная запись отключена"
            )

        await self.sessions.revoke_all_for_user(
            user.user_id,
            revoked_at=current_time,
            reason=SessionRevocationReason.PASSWORD_CHANGED.value,
        )
        created = self._prepare_session(
            user.user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            now=current_time,
        )
        await self._commit()
        await self.session.refresh(created.session)
        return created

    async def validate(
        self,
        session_token: str,
        *,
        now: datetime | None = None,
    ) -> UserSession:
        """Проверяет срок и владельца сессии и редко продлевает idle-таймер."""

        current_time = _utc_time(now)
        try:
            token_hash = hash_token(session_token)
        except ValueError as exc:
            raise InvalidSessionError("Недействительная сессия") from exc

        user_session = await self.sessions.get_by_token_hash(token_hash)
        if user_session is None or user_session.revoked_at is not None:
            raise InvalidSessionError("Недействительная сессия")

        if user_session.absolute_expires_at <= current_time:
            await self._revoke_invalid(
                user_session,
                current_time,
                SessionRevocationReason.ABSOLUTE_TIMEOUT,
            )
            raise InvalidSessionError("Недействительная сессия")

        if user_session.last_seen_at <= current_time - self._idle_lifetime:
            await self._revoke_invalid(
                user_session,
                current_time,
                SessionRevocationReason.IDLE_TIMEOUT,
            )
            raise InvalidSessionError("Недействительная сессия")

        if not user_session.user.is_active:
            await self._revoke_invalid(
                user_session,
                current_time,
                SessionRevocationReason.USER_INACTIVE,
            )
            raise InvalidSessionError("Недействительная сессия")

        touch_cutoff = current_time - self._touch_interval
        if user_session.last_seen_at <= touch_cutoff:
            touched = await self.sessions.touch_active(
                user_session.session_id,
                now=current_time,
            )
            if not touched:
                await self.session.rollback()
                raise InvalidSessionError("Недействительная сессия")
            user_session.last_seen_at = current_time
            await self._commit()

        return user_session

    async def revoke(
        self,
        session_token: str,
        *,
        reason: SessionRevocationReason = SessionRevocationReason.LOGOUT,
        now: datetime | None = None,
    ) -> bool:
        """Идемпотентно отзывает сессию по клиентскому токену."""

        try:
            token_hash = hash_token(session_token)
        except ValueError:
            return False
        user_session = await self.sessions.get_by_token_hash(token_hash)
        if user_session is None:
            return False

        changed = await self.sessions.revoke_session(
            user_session.session_id,
            revoked_at=_utc_time(now),
            reason=reason.value,
        )
        await self._commit()
        return changed

    async def revoke_all_for_user(
        self,
        user_id: int,
        *,
        reason: SessionRevocationReason = SessionRevocationReason.LOGOUT_ALL,
        except_session_id: int | None = None,
        now: datetime | None = None,
    ) -> int:
        """Отзывает все сессии пользователя или все, кроме текущей."""

        count = await self.sessions.revoke_all_for_user(
            user_id,
            revoked_at=_utc_time(now),
            reason=reason.value,
            except_session_id=except_session_id,
        )
        await self._commit()
        return count

    async def _revoke_invalid(
        self,
        user_session: UserSession,
        now: datetime,
        reason: SessionRevocationReason,
    ) -> None:
        await self.sessions.revoke_session(
            user_session.session_id,
            revoked_at=now,
            reason=reason.value,
        )
        await self._commit()

    def _prepare_session(
        self,
        user_id: int,
        *,
        client_ip: str | None,
        user_agent: str | None,
        now: datetime,
    ) -> CreatedSession:
        tokens = generate_session_tokens()
        user_session = UserSession(
            user_id=user_id,
            token_hash=hash_token(tokens.session_token),
            csrf_token_hash=hash_token(tokens.csrf_token),
            created_at=now,
            last_seen_at=now,
            absolute_expires_at=now + self._absolute_lifetime,
            ip_address=normalize_client_ip(client_ip),
            user_agent=normalize_user_agent(user_agent),
        )
        self.sessions.add(user_session)
        return CreatedSession(session=user_session, tokens=tokens)

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @property
    def _idle_lifetime(self) -> timedelta:
        return timedelta(minutes=self.settings.auth_session_idle_minutes)

    @property
    def _absolute_lifetime(self) -> timedelta:
        return timedelta(hours=self.settings.auth_session_absolute_hours)

    @property
    def _touch_interval(self) -> timedelta:
        return timedelta(minutes=self.settings.auth_session_touch_interval_minutes)


def _utc_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Время сессии должно содержать часовой пояс")
    return value.astimezone(UTC)
