"""Операции хранения пользователей."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from news_reposter.db.models import Role, User


class UserRepository:
    """Читает и добавляет учётные записи в рамках внешней транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[User]:
        """Возвращает пользователей вместе с назначенными ролями."""

        users = await self.session.scalars(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .order_by(User.display_name, User.user_id)
            .offset(offset)
            .limit(limit)
        )
        return list(users)

    async def get_by_normalized_username(self, username: str) -> User | None:
        """Возвращает пользователя по каноническому логину."""

        return await self.session.scalar(
            select(User).where(User.username_normalized == username)
        )

    async def get_by_id(self, user_id: int) -> User | None:
        """Возвращает пользователя по идентификатору без блокировки строки."""

        return await self.session.get(User, user_id)

    async def get_by_normalized_username_for_update(
        self,
        username: str,
    ) -> User | None:
        """Блокирует пользователя и перечитывает его актуальное состояние."""

        return await self.session.scalar(
            select(User)
            .where(User.username_normalized == username)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def get_by_id_for_update(self, user_id: int) -> User | None:
        """Блокирует пользователя по ID и перечитывает актуальное состояние."""

        return await self.session.scalar(
            select(User)
            .where(User.user_id == user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def add(self, user: User) -> None:
        """Добавляет пользователя в текущую транзакцию."""

        self.session.add(user)
