from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Post, QueueItem, QueueItemStatus, Target
from news_reposter.schemas.queue_item import QueueItemCreate, QueueItemUpdate


class QueueItemAlreadyExistsError(RuntimeError):
    """Такой пост уже добавлен в очередь выбранного целевого канала."""


class QueueItemRepository:
    """Выполняет операции с редакционной очередью постов."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def post_exists(self, post_id: int) -> bool:
        return await self.session.get(Post, post_id) is not None

    async def target_exists(self, target_id: int) -> bool:
        return await self.session.get(Target, target_id) is not None

    async def create(self, data: QueueItemCreate) -> QueueItem:
        item = QueueItem(**data.model_dump())
        self.session.add(item)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise QueueItemAlreadyExistsError from exc
        await self.session.refresh(item)
        return item

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        target_id: int | None,
        post_id: int | None,
        source_id: int | None,
        status: QueueItemStatus | None,
    ) -> list[QueueItem]:
        statement = select(QueueItem).order_by(QueueItem.queue_item_id)
        if source_id is not None:
            statement = statement.join(Post).where(Post.source_id == source_id)
        if target_id is not None:
            statement = statement.where(QueueItem.target_id == target_id)
        if post_id is not None:
            statement = statement.where(QueueItem.post_id == post_id)
        if status is not None:
            statement = statement.where(QueueItem.status == status)
        statement = statement.offset(offset).limit(limit)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get(self, queue_item_id: int) -> QueueItem | None:
        return await self.session.get(QueueItem, queue_item_id)

    async def update(self, item: QueueItem, data: QueueItemUpdate) -> QueueItem:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def set_status(
        self,
        item: QueueItem,
        new_status: QueueItemStatus,
        *,
        scheduled_at: datetime | None = None,
    ) -> QueueItem:
        item.status = new_status
        item.scheduled_at = scheduled_at
        item.error_message = None
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item: QueueItem) -> None:
        await self.session.delete(item)
        await self.session.commit()
