import asyncio
import logging

import httpx

from news_reposter.db.session import async_session_factory
from news_reposter.services.publisher import publish_due_items

logger = logging.getLogger(__name__)


class PublicationScheduler:
    """Проверяет запланированные публикации и отправляет наступившие в MAX."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        interval_seconds: int = 30,
    ) -> None:
        self._http_client = http_client
        self.interval_seconds = max(10, interval_seconds)
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="publication-scheduler")
        logger.info(
            "Планировщик публикаций запущен: проверка каждые %s сек",
            self.interval_seconds,
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                async with async_session_factory() as session:
                    from news_reposter.config import get_settings

                    if get_settings().background_tasks_enabled:
                        await enqueue_due_publications(session)
                        await session.commit()
                        continue
                    published, failed = await publish_due_items(
                        session,
                        self._http_client,
                    )
                if published or failed:
                    logger.info(
                        "Планировщик публикаций: опубликовано %s, ошибок %s",
                        published,
                        failed,
                    )
            except Exception:
                logger.exception("Ошибка фонового запуска публикаций")


async def enqueue_due_publications(session) -> int:
    from datetime import UTC, datetime

    from sqlalchemy import DateTime, exists, select

    from news_reposter.background.contracts import (
        ActiveTaskConflict,
        TaskQueue,
    )
    from news_reposter.background.intents import enqueue_scheduled_publication
    from news_reposter.db.models import BackgroundTask, QueueItem, QueueItemStatus
    from news_reposter.services.publisher import _loaded_item

    ids = list(
        await session.scalars(
            select(QueueItem.queue_item_id)
            .where(
                QueueItem.status == QueueItemStatus.SCHEDULED,
                QueueItem.scheduled_at <= datetime.now(UTC),
                ~exists().where(
                    BackgroundTask.subject_id == QueueItem.queue_item_id,
                    BackgroundTask.queue == TaskQueue.PUBLICATION,
                    BackgroundTask.payload["snapshot"]["scheduled_at"]
                    .as_string()
                    .cast(DateTime(timezone=True))
                    == QueueItem.scheduled_at,
                ),
            )
            .order_by(QueueItem.scheduled_at, QueueItem.queue_item_id)
            .limit(100)
        )
    )
    queued = 0
    for item_id in ids:
        item = await _loaded_item(session, item_id, for_update=True)
        if item is None or item.status != QueueItemStatus.SCHEDULED:
            continue
        try:
            await enqueue_scheduled_publication(session, item)
            queued += 1
        except ActiveTaskConflict:
            pass
    return queued
