from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Source, Target, TargetSource
from news_reposter.schemas import TargetSourceCreate, TargetSourceUpdate


class TargetSourceAlreadyExistsError(RuntimeError):
    """Источник уже подключён к этой цели публикации."""


class TargetSourceRepository:
    """Выполняет CRUD-операции со связями целей и источников."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def target_exists(self, target_id: int) -> bool:
        return await self.session.get(Target, target_id) is not None

    async def source_exists(self, source_id: int) -> bool:
        return await self.session.get(Source, source_id) is not None

    async def create(self, target_id: int, data: TargetSourceCreate) -> TargetSource:
        item = TargetSource(target_id=target_id, **data.model_dump())
        self.session.add(item)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise TargetSourceAlreadyExistsError from exc
        await self.session.refresh(item)
        return item

    async def list(
        self,
        *,
        target_id: int,
        offset: int,
        limit: int,
        is_active: bool | None,
    ) -> list[TargetSource]:
        statement = (
            select(TargetSource)
            .where(TargetSource.target_id == target_id)
            .order_by(TargetSource.target_source_id)
            .offset(offset)
            .limit(limit)
        )
        if is_active is not None:
            statement = statement.where(TargetSource.is_active == is_active)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get(self, target_id: int, target_source_id: int) -> TargetSource | None:
        statement = select(TargetSource).where(
            TargetSource.target_id == target_id,
            TargetSource.target_source_id == target_source_id,
        )
        return await self.session.scalar(statement)

    async def update(
        self,
        item: TargetSource,
        data: TargetSourceUpdate,
    ) -> TargetSource:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item: TargetSource) -> None:
        await self.session.delete(item)
        await self.session.commit()
