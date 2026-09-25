from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from news_reposter.db.models import (
    Post,
    Publication,
    QueueItem,
    QueueItemStatus,
    Target,
)
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

    async def create(self, data: QueueItemCreate, *, commit: bool = True) -> QueueItem:
        item = QueueItem(**data.model_dump())
        self.session.add(item)
        try:
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise QueueItemAlreadyExistsError from exc
        return await self.get(item.queue_item_id)  # type: ignore[return-value]

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        target_id: int | None,
        post_id: int | None,
        source_id: int | None,
        status: QueueItemStatus | None,
        allowed_target_ids: frozenset[int] | None = None,
    ) -> list[QueueItem]:
        statement = (
            select(QueueItem)
            .options(
                selectinload(QueueItem.post).selectinload(Post.attachments),
                selectinload(QueueItem.target),
                selectinload(QueueItem.publication).selectinload(
                    Publication.attempt_history
                ),
            )
            .order_by(QueueItem.queue_item_id.desc())
        )
        if source_id is not None:
            statement = statement.join(Post).where(Post.source_id == source_id)
        if target_id is not None:
            statement = statement.where(QueueItem.target_id == target_id)
        if post_id is not None:
            statement = statement.where(QueueItem.post_id == post_id)
        if status is not None:
            statement = statement.where(QueueItem.status == status)
        if allowed_target_ids is not None:
            statement = statement.where(QueueItem.target_id.in_(allowed_target_ids))
        statement = statement.offset(offset).limit(limit)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        target_id: int | None,
        statuses: list[QueueItemStatus],
        allowed_target_ids: frozenset[int] | None = None,
    ) -> list[QueueItem]:
        """Возвращает одну страницу очереди для выбранной группы статусов."""

        statement = (
            select(QueueItem)
            .options(
                selectinload(QueueItem.post).selectinload(Post.attachments),
                selectinload(QueueItem.target),
                selectinload(QueueItem.publication).selectinload(
                    Publication.attempt_history
                ),
            )
            .where(QueueItem.status.in_(statuses))
            .order_by(QueueItem.queue_item_id.desc())
        )
        if target_id is not None:
            statement = statement.where(QueueItem.target_id == target_id)
        if allowed_target_ids is not None:
            statement = statement.where(QueueItem.target_id.in_(allowed_target_ids))
        statement = statement.offset(offset).limit(limit)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def count_by_status(
        self,
        *,
        target_id: int | None,
        allowed_target_ids: frozenset[int] | None = None,
    ) -> dict[QueueItemStatus, int]:
        """Считает элементы каждого статуса для выбранного канала."""

        statement = select(
            QueueItem.status,
            func.count(QueueItem.queue_item_id),
        ).group_by(QueueItem.status)
        if target_id is not None:
            statement = statement.where(QueueItem.target_id == target_id)
        if allowed_target_ids is not None:
            statement = statement.where(QueueItem.target_id.in_(allowed_target_ids))
        rows = (await self.session.execute(statement)).all()
        return {queue_status: count for queue_status, count in rows}

    async def get(
        self,
        queue_item_id: int,
        *,
        allowed_target_ids: frozenset[int] | None = None,
    ) -> QueueItem | None:
        statement = (
            select(QueueItem)
            .options(
                selectinload(QueueItem.post).selectinload(Post.attachments),
                selectinload(QueueItem.target),
                selectinload(QueueItem.publication).selectinload(
                    Publication.attempt_history
                ),
            )
            .where(QueueItem.queue_item_id == queue_item_id)
        )
        if allowed_target_ids is not None:
            statement = statement.where(QueueItem.target_id.in_(allowed_target_ids))
        return await self.session.scalar(statement)

    async def update(
        self, item: QueueItem, data: QueueItemUpdate, *, commit: bool = True
    ) -> QueueItem:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return await self.get(item.queue_item_id)  # type: ignore[return-value]

    async def set_status(
        self,
        item: QueueItem,
        new_status: QueueItemStatus,
        *,
        scheduled_at: datetime | None = None,
        commit: bool = True,
    ) -> QueueItem:
        item.status = new_status
        item.scheduled_at = scheduled_at
        item.error_message = None
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return await self.get(item.queue_item_id)  # type: ignore[return-value]

    async def delete(self, item: QueueItem, *, commit: bool = True) -> None:
        await self.session.delete(item)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
