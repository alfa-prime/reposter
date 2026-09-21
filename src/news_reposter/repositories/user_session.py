"""Операции хранения серверных пользовательских сессий."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from news_reposter.db.models import Role, User, UserSession


class UserSessionRepository:
    """Работает с сессиями в рамках транзакции сервиса."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_user(self, user_id: int) -> User | None:
        """Блокирует пользователя до конца транзакции создания сессии."""

        return await self.session.scalar(
            select(User)
            .where(User.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def get_by_token_hash(self, token_hash: bytes) -> UserSession | None:
        """Возвращает сессию вместе с актуальными ролями и разрешениями."""

        return await self.session.scalar(
            select(UserSession)
            .where(UserSession.token_hash == token_hash)
            .options(
                selectinload(UserSession.user)
                .selectinload(User.roles)
                .selectinload(Role.permissions)
            )
        )

    async def list_usable_for_user(
        self,
        user_id: int,
        *,
        now: datetime,
        idle_cutoff: datetime,
    ) -> list[UserSession]:
        """Возвращает ещё не истёкшие сессии от старых к новым."""

        sessions = await self.session.scalars(
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.absolute_expires_at > now,
                UserSession.last_seen_at > idle_cutoff,
            )
            .order_by(UserSession.created_at, UserSession.session_id)
        )
        return list(sessions)

    def add(self, user_session: UserSession) -> None:
        """Добавляет новую сессию в текущую транзакцию."""

        self.session.add(user_session)

    async def revoke_session(
        self,
        session_id: int,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> bool:
        """Идемпотентно отзывает одну ещё активную сессию."""

        result = await self.session.execute(
            update(UserSession)
            .where(
                UserSession.session_id == session_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at, revoked_reason=reason)
        )
        return result.rowcount > 0

    async def revoke_all_for_user(
        self,
        user_id: int,
        *,
        revoked_at: datetime,
        reason: str,
        except_session_id: int | None = None,
    ) -> int:
        """Отзывает все сессии пользователя, кроме необязательного исключения."""

        statement = update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if except_session_id is not None:
            statement = statement.where(UserSession.session_id != except_session_id)

        result = await self.session.execute(
            statement.values(revoked_at=revoked_at, revoked_reason=reason)
        )
        return result.rowcount

    async def touch_active(
        self,
        session_id: int,
        *,
        now: datetime,
    ) -> bool:
        """Обновляет активность, только пока сессия не отозвана и не истекла."""

        result = await self.session.execute(
            update(UserSession)
            .where(
                UserSession.session_id == session_id,
                UserSession.revoked_at.is_(None),
                UserSession.absolute_expires_at > now,
            )
            .values(last_seen_at=now)
        )
        return result.rowcount > 0
