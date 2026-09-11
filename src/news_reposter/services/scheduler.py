import asyncio
import logging
import math
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from news_reposter.config import Settings
from news_reposter.services.collector import collect_active_sources_once

logger = logging.getLogger(__name__)


class CollectionScheduler:
    """Запускает сбор источников по настраиваемому дневному расписанию."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        try:
            self._timezone = ZoneInfo(settings.collection_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"Неизвестный часовой пояс: {settings.collection_timezone}"
            ) from exc

    def start(self) -> None:
        """Запускает фоновый цикл, если автоматический сбор включён."""

        if not self.settings.collection_enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="collection-scheduler")
        logger.info(
            "Планировщик сбора запущен: каждые %s мин, %02d:00-%02d:00, %s",
            self.settings.collection_interval_minutes,
            self.settings.collection_start_hour,
            self.settings.collection_end_hour,
            self.settings.collection_timezone,
        )

    async def stop(self) -> None:
        """Останавливает фоновый цикл при завершении приложения."""

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
            now = datetime.now(self._timezone)
            next_run = self.next_run_at(now)
            delay = max(0.0, (next_run - now).total_seconds())
            await asyncio.sleep(delay)

            try:
                await collect_active_sources_once()
            except Exception:
                logger.exception("Ошибка фонового запуска сбора источников")

    def next_run_at(self, now: datetime) -> datetime:
        """Возвращает ближайший момент запуска в часовом поясе планировщика."""

        if now.tzinfo is None:
            raise ValueError("now должен содержать часовой пояс")

        local_now = now.astimezone(self._timezone)
        start = datetime.combine(
            local_now.date(),
            time(hour=self.settings.collection_start_hour),
            tzinfo=self._timezone,
        )
        end = datetime.combine(
            local_now.date(),
            time(hour=self.settings.collection_end_hour),
            tzinfo=self._timezone,
        )

        if end <= start:
            raise ValueError("COLLECTION_END_HOUR должен быть позже COLLECTION_START_HOUR")

        if local_now <= start:
            return start
        if local_now >= end:
            return start + timedelta(days=1)

        interval_seconds = self.settings.collection_interval_minutes * 60
        elapsed_seconds = (local_now - start).total_seconds()
        step = math.ceil(elapsed_seconds / interval_seconds)
        candidate = start + timedelta(seconds=step * interval_seconds)

        if candidate >= end:
            return start + timedelta(days=1)
        return candidate
