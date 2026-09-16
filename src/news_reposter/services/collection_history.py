import re
from datetime import UTC, datetime

from sqlalchemy import update

from news_reposter.db.models import (
    CollectionRun,
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionSourceRun,
    CollectionSourceRunStatus,
)
from news_reposter.db.session import async_session_factory

_SECRET_PATTERN = re.compile(
    r"(?i)(access_token|token|authorization)(=|%3D|:\s*)([^&\s]+)"
)


def safe_error_message(error: BaseException) -> str:
    """Возвращает короткое сообщение без случайно попавших в него токенов."""

    message = str(error).strip() or error.__class__.__name__
    return _SECRET_PATTERN.sub(r"\1\2***", message)[:2000]


class CollectionHistory:
    """Записывает ход сбора независимо от транзакций с постами."""

    async def start_run(self, trigger: CollectionRunTrigger) -> int:
        async with async_session_factory() as session:
            run = CollectionRun(trigger=trigger, status=CollectionRunStatus.RUNNING)
            session.add(run)
            await session.commit()
            return run.collection_run_id

    async def set_sources_total(self, run_id: int, total: int) -> None:
        await self._update_run(run_id, sources_total=total)

    async def start_source(
        self,
        *,
        run_id: int,
        source_id: int,
        source_name: str,
        source_url: str,
        last_post_id_before: int | None,
    ) -> int:
        async with async_session_factory() as session:
            source_run = CollectionSourceRun(
                collection_run_id=run_id,
                source_id=source_id,
                source_name=source_name,
                source_url=source_url,
                status=CollectionSourceRunStatus.RUNNING,
                last_post_id_before=(
                    str(last_post_id_before)
                    if last_post_id_before is not None
                    else None
                ),
            )
            session.add(source_run)
            await session.commit()
            return source_run.collection_source_run_id

    async def finish_source(
        self,
        source_run_id: int,
        *,
        status: CollectionSourceRunStatus,
        last_post_id_after: int | None,
        posts_found: int,
        posts_created: int,
        queue_items_created: int,
        error: BaseException | None = None,
    ) -> None:
        values: dict[str, object] = {
            "status": status,
            "finished_at": datetime.now(UTC),
            "last_post_id_after": (
                str(last_post_id_after) if last_post_id_after is not None else None
            ),
            "posts_found": posts_found,
            "posts_created": posts_created,
            "queue_items_created": queue_items_created,
            "error_type": error.__class__.__name__ if error else None,
            "error_message": safe_error_message(error) if error else None,
        }
        async with async_session_factory() as session:
            await session.execute(
                update(CollectionSourceRun)
                .where(CollectionSourceRun.collection_source_run_id == source_run_id)
                .values(**values)
            )
            await session.commit()

    async def set_source_last_before(
        self, source_run_id: int, last_post_id: int | None
    ) -> None:
        async with async_session_factory() as session:
            await session.execute(
                update(CollectionSourceRun)
                .where(CollectionSourceRun.collection_source_run_id == source_run_id)
                .values(
                    last_post_id_before=(
                        str(last_post_id) if last_post_id is not None else None
                    )
                )
            )
            await session.commit()

    async def finish_run(
        self,
        run_id: int,
        *,
        status: CollectionRunStatus,
        summary: dict[str, int],
        error: BaseException | None = None,
    ) -> None:
        await self._update_run(
            run_id,
            status=status,
            finished_at=datetime.now(UTC),
            sources_total=summary["sources_total"],
            sources_checked=summary["sources_checked"],
            sources_succeeded=summary["sources_succeeded"],
            sources_failed=summary["errors"],
            posts_found=summary["posts_found"],
            posts_created=summary["posts_created"],
            queue_items_created=summary["queue_items_created"],
            error_message=safe_error_message(error) if error else None,
        )

    async def interrupt_stale_runs(self) -> None:
        """Закрывает записи, оставшиеся running после перезапуска приложения."""

        now = datetime.now(UTC)
        async with async_session_factory() as session:
            await session.execute(
                update(CollectionSourceRun)
                .where(CollectionSourceRun.status == CollectionSourceRunStatus.RUNNING)
                .values(
                    status=CollectionSourceRunStatus.INTERRUPTED,
                    finished_at=now,
                    error_message="Приложение было перезапущено во время сбора",
                )
            )
            await session.execute(
                update(CollectionRun)
                .where(CollectionRun.status == CollectionRunStatus.RUNNING)
                .values(
                    status=CollectionRunStatus.INTERRUPTED,
                    finished_at=now,
                    error_message="Приложение было перезапущено во время сбора",
                )
            )
            await session.commit()

    async def _update_run(self, run_id: int, **values: object) -> None:
        async with async_session_factory() as session:
            await session.execute(
                update(CollectionRun)
                .where(CollectionRun.collection_run_id == run_id)
                .values(**values)
            )
            await session.commit()
