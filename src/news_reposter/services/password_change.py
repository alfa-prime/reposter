"""Безопасная смена пользовательского пароля."""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.passwords import (
    MAX_PASSWORD_LENGTH,
    PasswordManager,
    PasswordValidationError,
)
from news_reposter.db.models import User
from news_reposter.repositories.user import UserRepository
from news_reposter.services.user_sessions import (
    CreatedSession,
    SessionUserUnavailableError,
    UserSessionService,
)


class CurrentPasswordInvalidError(RuntimeError):
    """Текущий пароль не соответствует сохранённому хешу."""


class PasswordUnchangedError(RuntimeError):
    """Новый пароль совпадает с текущим."""


class PasswordChangeUserUnavailableError(RuntimeError):
    """Пользователь исчез или был отключён во время запроса."""


@dataclass(frozen=True, slots=True)
class PasswordChangeResult:
    """Пользователь и секреты единственной новой сессии."""

    user: User
    created_session: CreatedSession = field(repr=False)


class PasswordChangeService:
    """Меняет пароль и одновременно ротирует все серверные сессии."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        password_manager: PasswordManager | None = None,
        user_repository: UserRepository | None = None,
        session_service: UserSessionService | None = None,
    ) -> None:
        self.session = session
        self.passwords = password_manager or PasswordManager()
        self.users = user_repository or UserRepository(session)
        self.user_sessions = session_service or UserSessionService(session)

    async def change(
        self,
        *,
        user_id: int,
        current_password: str,
        new_password: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
        now: datetime | None = None,
    ) -> PasswordChangeResult:
        """Проверяет текущий пароль и атомарно сохраняет новый."""

        user = await self.users.get_by_id_for_update(user_id)
        if user is None or not user.is_active:
            await self.session.rollback()
            raise PasswordChangeUserUnavailableError(
                "Пользователь не найден или его учётная запись отключена"
            )

        if not self._current_password_matches(current_password, user.password_hash):
            await self.session.rollback()
            raise CurrentPasswordInvalidError("Текущий пароль указан неверно")

        if new_password == current_password:
            await self.session.rollback()
            raise PasswordUnchangedError("Новый пароль должен отличаться от текущего")

        try:
            new_hash = self.passwords.hash(new_password)
        except PasswordValidationError:
            await self.session.rollback()
            raise
        user.password_hash = new_hash
        user.must_change_password = False

        try:
            created = await self.user_sessions.replace_after_password_change(
                user,
                client_ip=client_ip,
                user_agent=user_agent,
                now=now,
            )
        except SessionUserUnavailableError as exc:
            raise PasswordChangeUserUnavailableError(str(exc)) from exc
        except Exception:
            await self.session.rollback()
            raise

        return PasswordChangeResult(user=user, created_session=created)

    def _current_password_matches(
        self,
        password: str,
        password_hash: str,
    ) -> bool:
        if not 1 <= len(password) <= MAX_PASSWORD_LENGTH:
            return False
        return self.passwords.verify(password, password_hash)


__all__ = [
    "CurrentPasswordInvalidError",
    "PasswordChangeResult",
    "PasswordChangeService",
    "PasswordChangeUserUnavailableError",
    "PasswordUnchangedError",
]
