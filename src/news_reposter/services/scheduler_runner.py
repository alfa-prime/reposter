"""Dedicated leader for collection, publication and media cleanup schedules."""

import asyncio
import logging
import signal

from sqlalchemy import text

from news_reposter.db.session import close_database, engine
from news_reposter.http_client import create_http_client
from news_reposter.logging_config import configure_logging
from news_reposter.services.media_cleanup import MediaCleanupScheduler
from news_reposter.services.publication_scheduler import PublicationScheduler
from news_reposter.services.scheduler import CollectionScheduler

logger = logging.getLogger(__name__)
LOCK_KEY = 72285361924001001
RETRY_SECONDS = 5


async def run_schedulers(stop: asyncio.Event) -> None:
    """Hold a PostgreSQL session lock while any scheduler is running."""
    http_client = create_http_client()
    waiting_logged = False
    try:
        while not stop.is_set():
            try:
                async with engine.connect() as connection:
                    acquired = await connection.scalar(
                        text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
                    )
                    await connection.commit()
                    if acquired:
                        waiting_logged = False
                        collection = CollectionScheduler(http_client)
                        publication = PublicationScheduler(http_client)
                        cleanup = MediaCleanupScheduler()
                        try:
                            collection.start()
                            publication.start()
                            cleanup.start()
                            logger.info("Получено лидерство планировщиков")
                            while not stop.is_set():
                                try:
                                    await asyncio.wait_for(
                                        stop.wait(), timeout=RETRY_SECONDS
                                    )
                                except TimeoutError:
                                    await connection.execute(text("SELECT 1"))
                                    await connection.commit()
                        finally:
                            await collection.stop()
                            await publication.stop()
                            await cleanup.stop()
                            # Session locks survive rollback and pool return.
                            # Discard the connection to release leadership.
                            await connection.invalidate()
                    else:
                        if not waiting_logged:
                            logger.warning(
                                "Планировщики уже работают в другом процессе"
                            )
                            waiting_logged = True
            except asyncio.CancelledError:
                raise
            except Exception:
                waiting_logged = False
                logger.exception(
                    "Потеряно подключение планировщика; повтор через %s с",
                    RETRY_SECONDS,
                )
            if not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=RETRY_SECONDS)
                except TimeoutError:
                    pass
    finally:
        await http_client.aclose()
        await close_database()


def main() -> None:
    from news_reposter.config import get_settings

    configure_logging(get_settings().log_level)

    async def run() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        await run_schedulers(stop)

    asyncio.run(run())


if __name__ == "__main__":
    main()
