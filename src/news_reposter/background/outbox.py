"""At-least-once delivery; a broker adapter must return only after acceptance."""

import asyncio
from datetime import timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from news_reposter.background.contracts import TaskQueue, TaskState
from news_reposter.db.models import BackgroundTask, TaskDelivery, TaskOutbox
from news_reposter.db.session import async_session_factory


class Transport(Protocol):
    async def publish(self, task_id: UUID, queue: str, event_id: UUID) -> None: ...


class PostgresTransport:
    async def publish(self, task_id: UUID, queue: str, event_id: UUID) -> None:
        async with async_session_factory() as session:
            await session.execute(
                insert(TaskDelivery).values(task_id=task_id).on_conflict_do_nothing()
            )
            await session.commit()


async def reconcile_celery(*, limit: int = 100) -> int:
    """Redis may lose an accepted message; retry due tasks and old pending IDs."""
    async with async_session_factory() as session:
        rows = list(
            await session.scalars(
                select(TaskOutbox)
                .join(BackgroundTask, BackgroundTask.task_id == TaskOutbox.task_id)
                .where(
                    BackgroundTask.queue.in_(
                        [TaskQueue.REWRITE, TaskQueue.COLLECTION, TaskQueue.MAINTENANCE]
                    ),
                    TaskOutbox.delivered_at.is_not(None),
                    (TaskOutbox.lease_until.is_(None))
                    | (TaskOutbox.lease_until <= func.now()),
                    (
                        (BackgroundTask.state == TaskState.RETRY_WAIT)
                        & (BackgroundTask.available_at <= func.now())
                    )
                    | (
                        (BackgroundTask.state == TaskState.PENDING)
                        & (
                            TaskOutbox.delivered_at
                            <= func.now() - timedelta(seconds=120)
                        )
                    ),
                )
                .order_by(TaskOutbox.delivered_at)
                .with_for_update(of=TaskOutbox, skip_locked=True)
                .limit(limit)
            )
        )
        for row in rows:
            row.delivered_at = None
            row.available_at = await session.scalar(select(func.now()))
        await session.commit()
        return len(rows)


async def dispatch_once(transport: Transport) -> bool:
    async with async_session_factory() as session:
        row = await session.scalar(
            select(TaskOutbox)
            .where(
                TaskOutbox.delivered_at.is_(None),
                TaskOutbox.available_at <= func.now(),
                (TaskOutbox.lease_until.is_(None))
                | (TaskOutbox.lease_until <= func.now()),
            )
            .order_by(TaskOutbox.available_at, TaskOutbox.outbox_id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return False
        row.lease_token = token = uuid4()
        row.lease_until = await session.scalar(
            select(func.now() + timedelta(seconds=60))
        )
        row.attempts += 1
        task_id, queue, event_id, attempts = (
            row.task_id,
            row.queue,
            row.outbox_id,
            row.attempts,
        )
        await session.commit()
    # Never hold a DB row lock across a broker/network call.
    error = None
    try:
        async with asyncio.timeout(30):
            await transport.publish(task_id, queue, event_id)
    except Exception:
        error = "transport_unavailable"
    async with async_session_factory() as session:
        row = await session.scalar(
            select(TaskOutbox)
            .where(
                TaskOutbox.outbox_id == event_id,
                TaskOutbox.lease_token == token,
                TaskOutbox.lease_until > func.now(),
            )
            .with_for_update()
        )
        if row is None:
            return True  # Ownership expired: another dispatcher may redeliver safely.
        row.lease_token = row.lease_until = None
        row.error_code = error
        if error:
            # Transport availability is retried indefinitely with a capped delay.
            # The operation has not run; worker attempt budgets are independent.
            row.available_at = await session.scalar(
                select(func.now() + timedelta(seconds=min(300, 2 ** min(attempts, 8))))
            )
        else:
            row.delivered_at = await session.scalar(select(func.now()))
        await session.commit()
    return True
