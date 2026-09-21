"""Операции хранения пользователей."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import User


class UserRepository:
    """Читает и добавляет учётные записи в рамках внешней транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_normalized_username(self, username: str) -> User | None:
        """Возвращает пользователя по каноническому логину."""

        return await self.session.scalar(
            select(User).where(User.username_normalized == username)
        )

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

    def add(self, user: User) -> None:
        """Добавляет пользователя в текущую транзакцию."""

        self.session.add(user)
