"""Сценарии создания и административного управления пользователями."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.identity import prepare_display_name, prepare_username
from news_reposter.auth.passwords import PasswordManager
from news_reposter.auth.rbac import SystemRoleCode
from news_reposter.db.models import Role, User
from news_reposter.repositories.role import RoleRepository
from news_reposter.repositories.user import UserRepository
from news_reposter.repositories.user_session import UserSessionRepository
from news_reposter.services.user_sessions import SessionRevocationReason


class UserAlreadyExistsError(RuntimeError):
    """Учётная запись с таким нормализованным логином уже существует."""


class SystemRoleNotFoundError(RuntimeError):
    """Обязательная системная роль отсутствует или отключена."""


class UserNotFoundError(RuntimeError):
    """Пользователь не существует."""


class RolesNotFoundError(RuntimeError):
    """Одна или несколько назначаемых ролей отсутствуют или отключены."""

    def __init__(self, codes: set[str]) -> None:
        self.codes = codes
        super().__init__(f"Роли не найдены или отключены: {', '.join(sorted(codes))}")


class SelfManagementError(RuntimeError):
    """Администратор попытался лишить доступа собственную сессию."""


class UserService:
    """Создаёт пользователей, сохраняя транзакционные инварианты."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        password_manager: PasswordManager | None = None,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
        session_repository: UserSessionRepository | None = None,
    ) -> None:
        self.session = session
        self.password_manager = password_manager or PasswordManager()
        self.users = user_repository or UserRepository(session)
        self.roles = role_repository or RoleRepository(session)
        self.user_sessions = session_repository or UserSessionRepository(session)

    async def list_users(self) -> list[User]:
        """Возвращает первые сто пользователей для административного списка."""

        return await self.users.list(limit=100)

    async def list_roles(self) -> list[Role]:
        """Возвращает роли, которые можно назначить пользователю."""

        return await self.roles.list_active()

    async def create_user(
        self,
        *,
        username: str,
        display_name: str,
        temporary_password: str,
        role_codes: list[str],
    ) -> User:
        """Создаёт активного пользователя, обязанного заменить временный пароль."""

        prepared_username = prepare_username(username)
        prepared_display_name = prepare_display_name(display_name)
        existing = await self.users.get_by_normalized_username(
            prepared_username.normalized
        )
        if existing is not None:
            raise UserAlreadyExistsError(
                f"Пользователь с логином {prepared_username.normalized!r} уже существует"
            )

        assigned_roles = await self._resolve_roles(set(role_codes))
        user = User(
            username=prepared_username.value,
            username_normalized=prepared_username.normalized,
            display_name=prepared_display_name,
            password_hash=self.password_manager.hash(temporary_password),
            is_active=True,
            must_change_password=True,
            roles=assigned_roles,
        )
        self.users.add(user)
        await self._commit_new_user(user, prepared_username.normalized)
        return user

    async def update_user(
        self,
        user_id: int,
        *,
        actor_user_id: int,
        display_name: str | None = None,
        is_active: bool | None = None,
        role_codes: list[str] | None = None,
    ) -> User:
        """Изменяет имя, активность и полный набор ролей пользователя."""

        user = await self.users.get_by_id_for_update(user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден")
        if user_id == actor_user_id and (is_active is False or role_codes is not None):
            raise SelfManagementError(
                "Нельзя отключить собственную учётную запись или изменить свои роли"
            )

        if display_name is not None:
            user.display_name = prepare_display_name(display_name)
        if role_codes is not None:
            user.roles = await self._resolve_roles(set(role_codes))
        if is_active is not None:
            user.is_active = is_active
            if not is_active:
                await self.user_sessions.revoke_all_for_user(
                    user.user_id,
                    revoked_at=datetime.now(UTC),
                    reason=SessionRevocationReason.ADMIN_REVOKED.value,
                )

        await self._commit()
        await self._refresh_admin_user(user)
        return user

    async def reset_password(
        self,
        user_id: int,
        *,
        actor_user_id: int,
        temporary_password: str,
    ) -> User:
        """Устанавливает временный пароль и завершает все сессии пользователя."""

        if user_id == actor_user_id:
            raise SelfManagementError(
                "Свой пароль нужно менять через меню текущего пользователя"
            )
        user = await self.users.get_by_id_for_update(user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден")

        user.password_hash = self.password_manager.hash(temporary_password)
        user.must_change_password = True
        await self.user_sessions.revoke_all_for_user(
            user.user_id,
            revoked_at=datetime.now(UTC),
            reason=SessionRevocationReason.ADMIN_REVOKED.value,
        )
        await self._commit()
        await self._refresh_admin_user(user)
        return user

    async def revoke_sessions(
        self,
        user_id: int,
        *,
        actor_user_id: int,
    ) -> int:
        """Завершает все активные сессии другого пользователя."""

        if user_id == actor_user_id:
            raise SelfManagementError(
                "Свои сессии нужно завершать через меню текущего пользователя"
            )
        user = await self.users.get_by_id_for_update(user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден")
        count = await self.user_sessions.revoke_all_for_user(
            user.user_id,
            revoked_at=datetime.now(UTC),
            reason=SessionRevocationReason.ADMIN_REVOKED.value,
        )
        await self._commit()
        return count

    async def create_administrator(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
    ) -> User:
        """Создаёт активного администратора с уже установленным паролем."""

        prepared_username = prepare_username(username)
        prepared_display_name = prepare_display_name(display_name)

        existing = await self.users.get_by_normalized_username(
            prepared_username.normalized
        )
        if existing is not None:
            raise UserAlreadyExistsError(
                f"Пользователь с логином {prepared_username.normalized!r} уже существует"
            )

        administrator_role = await self.roles.get_by_code(
            SystemRoleCode.ADMINISTRATOR.value
        )
        if administrator_role is None:
            raise SystemRoleNotFoundError(
                "Системная роль administrator не найдена или отключена; "
                "проверьте применение миграций"
            )

        user = User(
            username=prepared_username.value,
            username_normalized=prepared_username.normalized,
            display_name=prepared_display_name,
            password_hash=self.password_manager.hash(password),
            is_active=True,
            must_change_password=False,
            roles=[administrator_role],
        )
        self.users.add(user)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            concurrent_user = await self.users.get_by_normalized_username(
                prepared_username.normalized
            )
            if concurrent_user is not None:
                raise UserAlreadyExistsError(
                    "Пользователь с логином "
                    f"{prepared_username.normalized!r} уже существует"
                ) from exc
            raise

        await self.session.refresh(user)
        return user

    async def _resolve_roles(self, codes: set[str]) -> list[Role]:
        if not codes:
            raise RolesNotFoundError(codes)
        roles = await self.roles.get_active_by_codes(codes)
        found_codes = {role.code for role in roles}
        missing_codes = codes - found_codes
        if missing_codes:
            raise RolesNotFoundError(missing_codes)
        return roles

    async def _commit_new_user(self, user: User, normalized_username: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            concurrent_user = await self.users.get_by_normalized_username(
                normalized_username
            )
            if concurrent_user is not None:
                raise UserAlreadyExistsError(
                    f"Пользователь с логином {normalized_username!r} уже существует"
                ) from exc
            raise
        await self._refresh_admin_user(user)

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def _refresh_admin_user(self, user: User) -> None:
        """Обновляет серверные поля, не сбрасывая уже загруженные роли."""

        await self.session.refresh(
            user,
            attribute_names=["user_id", "created_at", "updated_at", "last_login_at"],
        )
