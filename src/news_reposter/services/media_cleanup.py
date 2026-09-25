from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from sqlalchemy import select

from news_reposter.config import get_settings
from news_reposter.db.models import QueueItem
from news_reposter.db.session import async_session_factory
from news_reposter.services import media_storage

logger = logging.getLogger(__name__)


def cleanup_orphaned_media(
    media_root: Path,
    active_queue_item_ids: set[int],
    *,
    now: float | None = None,
) -> tuple[int, int]:
    """Удаляет старые временные файлы и давно осиротевшие каталоги."""

    settings = get_settings()
    current = time.time() if now is None else now
    temp_cutoff = current - settings.media_temp_max_age_hours * 3600
    orphan_cutoff = current - settings.media_orphan_max_age_days * 86400
    removed_temp = 0
    removed_orphans = 0
    if not media_root.exists():
        return removed_temp, removed_orphans

    for temporary in media_root.rglob(".upload-*.part"):
        if temporary.is_file() and temporary.stat().st_mtime < temp_cutoff:
            temporary.unlink(missing_ok=True)
            removed_temp += 1

    for directory in media_root.iterdir():
        if not directory.is_dir() or not directory.name.isdigit():
            continue
        queue_item_id = int(directory.name)
        if queue_item_id in active_queue_item_ids:
            continue
        newest = max(
            (path.stat().st_mtime for path in directory.rglob("*") if path.exists()),
            default=directory.stat().st_mtime,
        )
        if newest < orphan_cutoff:
            shutil.rmtree(directory)
            removed_orphans += 1

    state_directory = media_root / "_state"
    if state_directory.exists():
        for state in state_directory.glob("*.json"):
            if (
                state.stem.isdigit()
                and int(state.stem) not in active_queue_item_ids
                and state.stat().st_mtime < orphan_cutoff
            ):
                state.unlink(missing_ok=True)
    return removed_temp, removed_orphans


class MediaCleanupScheduler:
    """Ежедневно убирает незавершённые загрузки и потерянные медиа."""

    def __init__(self, interval_seconds: int = 24 * 3600) -> None:
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="media-cleanup")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def run_once(self) -> tuple[int, int]:
        async with async_session_factory() as session:
            ids = set((await session.scalars(select(QueueItem.queue_item_id))).all())
        result = await asyncio.to_thread(
            cleanup_orphaned_media, media_storage.MEDIA_ROOT, ids
        )
        if any(result):
            logger.info(
                "Очистка медиа: временных файлов %s, потерянных каталогов %s",
                result[0],
                result[1],
            )
        return result

    async def _run(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Ошибка фоновой очистки медиа")
            await asyncio.sleep(self.interval_seconds)
