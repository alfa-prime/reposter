"""Операции чтения ролей."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

    async def list_active(self) -> list[Role]:
        """Возвращает активные роли и их разрешения для админки."""

        roles = await self.session.scalars(
            select(Role)
            .where(Role.is_active.is_(True))
            .options(selectinload(Role.permissions))
            .order_by(Role.name, Role.role_id)
        )
        return list(roles)

    async def get_active_by_codes(self, codes: set[str]) -> list[Role]:
        """Возвращает активные роли из заданного набора кодов."""

        if not codes:
            return []
        roles = await self.session.scalars(
            select(Role)
            .where(Role.code.in_(codes), Role.is_active.is_(True))
            .options(selectinload(Role.permissions))
            .order_by(Role.name, Role.role_id)
        )
        return list(roles)
