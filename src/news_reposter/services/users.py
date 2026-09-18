"""Сценарии управления учётными записями."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.identity import prepare_display_name, prepare_username
from news_reposter.auth.passwords import PasswordManager
from news_reposter.auth.rbac import SystemRoleCode
from news_reposter.db.models import User
from news_reposter.repositories.role import RoleRepository
from news_reposter.repositories.user import UserRepository


class UserAlreadyExistsError(RuntimeError):
    """Учётная запись с таким нормализованным логином уже существует."""


class SystemRoleNotFoundError(RuntimeError):
    """Обязательная системная роль отсутствует или отключена."""


class UserService:
    """Создаёт пользователей, сохраняя транзакционные инварианты."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        password_manager: PasswordManager | None = None,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
    ) -> None:
        self.session = session
        self.password_manager = password_manager or PasswordManager()
        self.users = user_repository or UserRepository(session)
        self.roles = role_repository or RoleRepository(session)

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
