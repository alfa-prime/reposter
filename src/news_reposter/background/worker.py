"""One queue per process; short DB transactions around external work."""

import argparse
import asyncio
import logging
from contextlib import suppress

from news_reposter.background.contracts import (
    POLICIES,
    LostLease,
    PermanentTaskError,
    RetryableTaskError,
    ReviewRequired,
    TaskQueue,
    TaskState,
)
from news_reposter.background.handlers import HANDLERS, classify_error
from news_reposter.background.outbox import PostgresTransport, dispatch_once
from news_reposter.background.store import claim, finish, heartbeat, recover_expired
from news_reposter.config import get_settings
from news_reposter.db.session import async_session_factory, close_database
from news_reposter.http_client import create_http_client

logger = logging.getLogger(__name__)


async def run_once(queue: TaskQueue, client) -> bool:
    settings = get_settings()
    async with async_session_factory() as session:
        await recover_expired(session)
        task = await claim(session, queue, settings.background_task_lease_seconds)
        await session.commit()
    if task is None:
        return False
    token = task.lease_token
    execution = None

    async def renew():
        while True:
            await asyncio.sleep(settings.background_task_lease_seconds / 3)
            try:
                async with async_session_factory() as session:
                    alive = await heartbeat(
                        session,
                        task.task_id,
                        token,
                        settings.background_task_lease_seconds,
                    )
                    await session.commit()
                if not alive:
                    if execution:
                        execution.cancel()
                    return
            except Exception:
                # Conservatively cancel if ownership cannot be proven.
                if execution:
                    execution.cancel()
                return

    async def execute():
        async with asyncio.timeout(POLICIES[queue].timeout_seconds):
            completion = await HANDLERS[queue](task, client)
            if completion.completed:
                return
            async with async_session_factory() as session:
                await finish(
                    session,
                    task.task_id,
                    token,
                    TaskState.SUCCEEDED,
                    result=completion.result,
                    apply=completion.apply,
                )
                await session.commit()

    execution = asyncio.create_task(execute())
    renewal = asyncio.create_task(renew())
    try:
        await execution
    except LostLease:
        logger.warning("action=task_finish status=lease_lost task_id=%s", task.task_id)
    except asyncio.CancelledError:
        # Leave RUNNING for bounded lease recovery; publication must not auto-retry.
        if asyncio.current_task().cancelling():
            raise
        logger.warning("action=task_finish status=lease_lost task_id=%s", task.task_id)
    except Exception as original:
        error = classify_error(original)
        if isinstance(error, ReviewRequired) or (
            queue == TaskQueue.PUBLICATION
            and not isinstance(original, (PermanentTaskError, RetryableTaskError))
        ):
            state = TaskState.NEEDS_REVIEW
        elif (
            isinstance(error, RetryableTaskError) and task.attempts < task.max_attempts
        ):
            state = TaskState.RETRY_WAIT
        else:
            state = TaskState.FAILED
        delay = POLICIES[queue].delay(
            task.attempts, getattr(error, "retry_after", None)
        )
        async with async_session_factory() as session:
            try:
                await finish(
                    session,
                    task.task_id,
                    token,
                    state,
                    code=str(error)[:100],
                    delay=delay,
                )
                await session.commit()
            except LostLease:
                await session.rollback()
        logger.warning(
            "action=task_finish task_id=%s state=%s error_type=%s",
            task.task_id,
            state,
            type(original).__name__,
        )
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError):
            await renewal
    return True


async def serve(queue: TaskQueue | None, once: bool) -> None:
    client = create_http_client()
    try:
        while True:
            worked = await (
                dispatch_once(PostgresTransport())
                if queue is None
                else run_once(queue, client)
            )
            if once:
                break
            if not worked:
                await asyncio.sleep(get_settings().background_task_poll_seconds)
    finally:
        await client.aclose()
        await close_database()


async def recover_only() -> None:
    try:
        async with async_session_factory() as session:
            count = await recover_expired(session)
            await session.commit()
            logger.info("action=task_recovery count=%s", count)
    finally:
        await close_database()


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--queue", choices=[queue.value for queue in TaskQueue])
    mode.add_argument("--dispatch", action="store_true")
    mode.add_argument("--recover", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.recover:
        asyncio.run(recover_only())
    else:
        asyncio.run(serve(TaskQueue(args.queue) if args.queue else None, args.once))


if __name__ == "__main__":
    main()
