"""Хранение и сериализация попыток входа."""

from datetime import datetime

from sqlalchemy import BigInteger, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import LoginAttempt


class LoginAttemptRepository:
    """Работает с журналом входов в рамках транзакции аутентификации."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acquire_rate_limit_locks(self, lock_keys: list[int]) -> None:
        """Сериализует конкурентные входы по логину и IP до конца транзакции."""

        for lock_key in sorted(set(lock_keys)):
            await self.session.execute(
                select(func.pg_advisory_xact_lock(literal(lock_key, type_=BigInteger)))
            )

    async def recent_failed_by_username(
        self,
        fingerprint: bytes,
        *,
        limit: int,
    ) -> list[datetime]:
        """Возвращает последние неудачи для логина от новой к старой."""

        timestamps = await self.session.scalars(
            select(LoginAttempt.attempted_at)
            .where(
                LoginAttempt.username_fingerprint == fingerprint,
                LoginAttempt.was_successful.is_(False),
            )
            .order_by(LoginAttempt.attempted_at.desc())
            .limit(limit)
        )
        return list(timestamps)

    async def recent_failed_by_ip(
        self,
        client_ip: str,
        *,
        limit: int,
    ) -> list[datetime]:
        """Возвращает последние неудачи с IP от новой к старой."""

        timestamps = await self.session.scalars(
            select(LoginAttempt.attempted_at)
            .where(
                LoginAttempt.ip_address == client_ip,
                LoginAttempt.was_successful.is_(False),
            )
            .order_by(LoginAttempt.attempted_at.desc())
            .limit(limit)
        )
        return list(timestamps)

    def add(self, attempt: LoginAttempt) -> None:
        """Добавляет результат проверки в текущую транзакцию."""

        self.session.add(attempt)
