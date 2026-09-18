"""Операции чтения ролей."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Role


class RoleRepository:
    """Находит роли в рамках переданной SQLAlchemy-сессии."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, code: str) -> Role | None:
        """Возвращает активную роль по стабильному коду."""

        return await self.session.scalar(
            select(Role).where(Role.code == code, Role.is_active.is_(True))
        )
