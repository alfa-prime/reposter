"""Сценарии создания и административного управления пользователями."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.identity import prepare_display_name, prepare_username
from news_reposter.auth.passwords import PasswordManager
from news_reposter.auth.rbac import SystemRoleCode
from news_reposter.db.models import AuditEvent, Role, Target, User
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


class RoleCombinationError(RuntimeError):
    """Набор ролей содержит взаимоисключающие назначения."""


class SelfManagementError(RuntimeError):
    """Администратор попытался лишить доступа собственную сессию."""


class TargetsNotFoundError(RuntimeError):
    """Один или несколько назначаемых каналов не существуют."""

    def __init__(self, target_ids: set[int]) -> None:
        self.target_ids = target_ids
        super().__init__(
            f"Каналы не найдены: {', '.join(map(str, sorted(target_ids)))}"
        )


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
        target_ids: list[int] | None = None,
        actor_user_id: int | None = None,
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
        assigned_targets = (
            []
            if self._has_administrator_role(assigned_roles)
            else await self._resolve_targets(set(target_ids or []))
        )
        user = User(
            username=prepared_username.value,
            username_normalized=prepared_username.normalized,
            display_name=prepared_display_name,
            password_hash=self.password_manager.hash(temporary_password),
            is_active=True,
            must_change_password=True,
            roles=assigned_roles,
            targets=assigned_targets,
        )
        self.users.add(user)
        await self.session.flush()
        if actor_user_id is not None:
            self._record_audit(
                actor_user_id=actor_user_id,
                action="user.created",
                user_id=user.user_id,
                details={
                    "role_codes": sorted(role.code for role in assigned_roles),
                    "target_ids": sorted(
                        target.target_id for target in assigned_targets
                    ),
                },
            )
            self._record_target_assignment(
                actor_user_id=actor_user_id,
                user_id=user.user_id,
                previous_ids=set(),
                current_ids={target.target_id for target in assigned_targets},
            )
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
        target_ids: list[int] | None = None,
    ) -> User:
        """Изменяет имя, активность и полный набор ролей пользователя."""

        user = await self.users.get_by_id_for_update(user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден")
        if user_id == actor_user_id and (is_active is False or role_codes is not None):
            raise SelfManagementError(
                "Нельзя отключить собственную учётную запись или изменить свои роли"
            )

        previous_target_ids = {target.target_id for target in user.targets}
        previous_role_codes = {role.code for role in user.roles}
        previous_display_name = user.display_name
        previous_is_active = user.is_active
        if display_name is not None:
            user.display_name = prepare_display_name(display_name)
        if role_codes is not None:
            user.roles = await self._resolve_roles(set(role_codes))
        if self._has_administrator_role(user.roles):
            user.targets = []
        elif target_ids is not None:
            user.targets = await self._resolve_targets(set(target_ids))
        current_target_ids = {target.target_id for target in user.targets}
        if previous_target_ids != current_target_ids:
            self._record_target_assignment(
                actor_user_id=actor_user_id,
                user_id=user.user_id,
                previous_ids=previous_target_ids,
                current_ids=current_target_ids,
            )
        if is_active is not None:
            user.is_active = is_active
            if not is_active:
                await self.user_sessions.revoke_all_for_user(
                    user.user_id,
                    revoked_at=datetime.now(UTC),
                    reason=SessionRevocationReason.ADMIN_REVOKED.value,
                )

        changed: dict[str, object] = {}
        if user.display_name != previous_display_name:
            changed["display_name"] = {
                "previous": previous_display_name,
                "current": user.display_name,
            }
        current_role_codes = {role.code for role in user.roles}
        if current_role_codes != previous_role_codes:
            changed["role_codes"] = {
                "previous": sorted(previous_role_codes),
                "current": sorted(current_role_codes),
            }
        if user.is_active != previous_is_active:
            changed["is_active"] = {
                "previous": previous_is_active,
                "current": user.is_active,
            }
        if changed:
            self._record_audit(
                actor_user_id=actor_user_id,
                action="user.updated",
                user_id=user.user_id,
                details=changed,
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
        self._record_audit(
            actor_user_id=actor_user_id,
            action="user.password.reset",
            user_id=user.user_id,
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
        self._record_audit(
            actor_user_id=actor_user_id,
            action="user.sessions.revoked",
            user_id=user.user_id,
            details={"revoked_sessions": count},
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
        if SystemRoleCode.ADMINISTRATOR.value in codes and len(codes) > 1:
            raise RoleCombinationError(
                "Роль administrator уже включает все разрешения и назначается отдельно"
            )
        roles = await self.roles.get_active_by_codes(codes)
        found_codes = {role.code for role in roles}
        missing_codes = codes - found_codes
        if missing_codes:
            raise RolesNotFoundError(missing_codes)
        return roles

    async def _resolve_targets(self, target_ids: set[int]) -> list[Target]:
        if not target_ids:
            return []
        targets = list(
            (
                await self.session.scalars(
                    select(Target).where(Target.target_id.in_(target_ids))
                )
            ).all()
        )
        missing_ids = target_ids - {target.target_id for target in targets}
        if missing_ids:
            raise TargetsNotFoundError(missing_ids)
        return targets

    @staticmethod
    def _has_administrator_role(roles: list[Role]) -> bool:
        return any(role.code == SystemRoleCode.ADMINISTRATOR.value for role in roles)

    def _record_target_assignment(
        self,
        *,
        actor_user_id: int,
        user_id: int,
        previous_ids: set[int],
        current_ids: set[int],
    ) -> None:
        if previous_ids == current_ids:
            return
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action="user.targets.changed",
                subject_type="user",
                subject_id=user_id,
                details={
                    "previous_target_ids": sorted(previous_ids),
                    "target_ids": sorted(current_ids),
                    "added_target_ids": sorted(current_ids - previous_ids),
                    "removed_target_ids": sorted(previous_ids - current_ids),
                },
            )
        )

    def _record_audit(
        self,
        *,
        actor_user_id: int,
        action: str,
        user_id: int,
        details: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                subject_type="user",
                subject_id=user_id,
                details=details or {},
            )
        )

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
