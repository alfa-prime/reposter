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
