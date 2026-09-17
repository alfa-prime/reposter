import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from news_reposter.db.models import CollectionRunTrigger, CollectionSettings
from news_reposter.db.session import async_session_factory
from news_reposter.repositories.collection import CollectionRepository
from news_reposter.services.collection_history import CollectionHistory
from news_reposter.services.collector import (
    CollectionAlreadyRunningError,
    collect_active_sources_once,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CollectionSchedule:
    """Снимок настроек, безопасный для использования после закрытия сессии."""

    enabled: bool
    interval_minutes: int
    start_time: time
    end_time: time
    timezone: str

    @classmethod
    def from_model(cls, settings: CollectionSettings) -> "CollectionSchedule":
        return cls(
            enabled=settings.enabled,
            interval_minutes=settings.interval_minutes,
            start_time=settings.start_time,
            end_time=settings.end_time,
            timezone=settings.timezone,
        )

    def zoneinfo(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Неизвестный часовой пояс: {self.timezone}") from exc


async def load_collection_schedule() -> CollectionSchedule:
    async with async_session_factory() as session:
        settings = await CollectionRepository(session).get_settings()
        return CollectionSchedule.from_model(settings)


def next_run_at(now: datetime, schedule: CollectionSchedule) -> datetime:
    """Считает ближайший запуск для дневного или ночного рабочего периода."""

    if now.tzinfo is None:
        raise ValueError("now должен содержать часовой пояс")
    if schedule.start_time == schedule.end_time:
        raise ValueError("Начало и окончание периода не должны совпадать")

    timezone = schedule.zoneinfo()
    local_now = now.astimezone(timezone)
    today = local_now.date()

    if schedule.start_time < schedule.end_time:
        today_start = datetime.combine(today, schedule.start_time, timezone)
        today_end = datetime.combine(today, schedule.end_time, timezone)
        if local_now < today_start:
            window_start, window_end = today_start, today_end
        elif local_now < today_end:
            window_start, window_end = today_start, today_end
        else:
            window_start = datetime.combine(
                today + timedelta(days=1), schedule.start_time, timezone
            )
            window_end = datetime.combine(
                today + timedelta(days=1), schedule.end_time, timezone
            )
    elif local_now.timetz().replace(tzinfo=None) >= schedule.start_time:
        window_start = datetime.combine(today, schedule.start_time, timezone)
        window_end = datetime.combine(
            today + timedelta(days=1), schedule.end_time, timezone
        )
    elif local_now.timetz().replace(tzinfo=None) < schedule.end_time:
        window_start = datetime.combine(
            today - timedelta(days=1), schedule.start_time, timezone
        )
        window_end = datetime.combine(today, schedule.end_time, timezone)
    else:
        window_start = datetime.combine(today, schedule.start_time, timezone)
        window_end = datetime.combine(
            today + timedelta(days=1), schedule.end_time, timezone
        )

    if local_now <= window_start:
        return window_start

    interval_seconds = schedule.interval_minutes * 60
    elapsed_seconds = (local_now - window_start).total_seconds()
    step = math.ceil(elapsed_seconds / interval_seconds)
    candidate = window_start + timedelta(seconds=step * interval_seconds)
    if candidate < window_end:
        return candidate

    next_date = window_start.date() + timedelta(days=1)
    return datetime.combine(next_date, schedule.start_time, timezone)


class CollectionScheduler:
    """Запускает сбор по сохранённому в PostgreSQL расписанию."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client
        self._task: asyncio.Task[None] | None = None
        self._settings_changed = asyncio.Event()

    def start(self) -> None:
        """Запускает цикл; отключённое расписание будет ждать настройки из UI."""

        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="collection-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def notify_settings_changed(self) -> None:
        """Немедленно пересчитывает ожидание после сохранения настроек."""

        self._settings_changed.set()

    async def _wait_for_change(self, timeout: float | None = None) -> bool:
        try:
            if timeout is None:
                await self._settings_changed.wait()
            else:
                await asyncio.wait_for(self._settings_changed.wait(), timeout)
        except TimeoutError:
            return False
        self._settings_changed.clear()
        return True

    async def _run(self) -> None:
        try:
            await CollectionHistory().interrupt_stale_runs()
        except Exception:
            logger.exception("Не удалось закрыть прерванные запуски сборщика")

        while True:
            try:
                schedule = await load_collection_schedule()
                if not schedule.enabled:
                    logger.info("Автоматический сбор отключён")
                    await self._wait_for_change()
                    continue

                now = datetime.now(schedule.zoneinfo())
                next_run = next_run_at(now, schedule)
                logger.info("Следующий автоматический сбор: %s", next_run.isoformat())
                if await self._wait_for_change(
                    max(0.0, (next_run - now).total_seconds())
                ):
                    continue
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except CollectionAlreadyRunningError:
                logger.info("Плановый сбор пропущен: другой сбор уже выполняется")
            except Exception:
                logger.exception(
                    "Ошибка фонового запуска сборщика; повтор через минуту"
                )
                await self._wait_for_change(60)

    async def run_once(self) -> dict[str, int]:
        summary = await collect_active_sources_once(
            self._http_client,
            CollectionRunTrigger.SCHEDULED,
        )
        logger.info(
            "Плановый сбор завершён: источников %s, постов %s, очередь %s, ошибок %s",
            summary["sources_checked"],
            summary["posts_created"],
            summary["queue_items_created"],
            summary["errors"],
        )
        return summary
