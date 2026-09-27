"""Short transactions, DB uniqueness, expiring ownership, fenced completion."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.background.contracts import (
    POLICIES,
    ActiveTaskConflict,
    IdempotencyConflict,
    LostLease,
    TaskQueue,
    TaskState,
)
from news_reposter.db.models import (
    BackgroundTask,
    CollectionRun,
    CollectionRunStatus,
    CollectionSourceRun,
    CollectionSourceRunStatus,
    Publication,
    PublicationAttempt,
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItem,
    QueueItemStatus,
    TaskDelivery,
    TaskOutbox,
)


async def enqueue(
    session: AsyncSession,
    queue: TaskQueue,
    key: str,
    payload: dict,
    *,
    actor_user_id: int | None = None,
    subject_id: int | None = None,
    target_id: int | None = None,
    available_at=None,
) -> BackgroundTask:
    """Caller commits business changes, task and outbox together. Never commits here."""
    if not key or len(key) > 200:
        raise ValueError("invalid idempotency key")
    digest = hashlib.sha256(
        json.dumps(
            [queue, payload, actor_user_id, subject_id, target_id],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    values = dict(
        task_id=uuid4(),
        queue=queue,
        state=TaskState.PENDING,
        idempotency_key=key,
        payload_hash=digest,
        payload=payload,
        actor_user_id=actor_user_id,
        subject_id=subject_id,
        target_id=target_id,
        max_attempts=POLICIES[queue].max_attempts,
    )
    if available_at is not None:
        values["available_at"] = available_at
    try:
        async with session.begin_nested():
            task_id = await session.scalar(
                insert(BackgroundTask)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[BackgroundTask.idempotency_key])
                .returning(BackgroundTask.task_id)
            )
            if task_id is not None:
                session.add(
                    TaskOutbox(
                        task_id=task_id,
                        queue=queue.value,
                        **({"available_at": available_at} if available_at else {}),
                    )
                )
                await session.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ActiveTaskConflict("active_task_exists") from exc
        raise
    task = await session.scalar(
        select(BackgroundTask).where(BackgroundTask.idempotency_key == key)
    )
    if task.payload_hash != digest:
        raise IdempotencyConflict("idempotency_key_reused_with_different_payload")
    return task


async def claim(
    session: AsyncSession, queue: TaskQueue, lease_seconds: int
) -> BackgroundTask | None:
    task = await session.scalar(
        select(BackgroundTask)
        .where(
            BackgroundTask.queue == queue,
            BackgroundTask.state.in_([TaskState.PENDING, TaskState.RETRY_WAIT]),
            BackgroundTask.available_at <= func.now(),
            exists().where(TaskDelivery.task_id == BackgroundTask.task_id),
        )
        .order_by(
            BackgroundTask.available_at,
            BackgroundTask.created_at,
            BackgroundTask.task_id,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if task is None:
        return None
    task.state = TaskState.RUNNING
    task.attempts += 1
    task.lease_token = uuid4()
    task.lease_until = await session.scalar(
        select(func.now() + timedelta(seconds=lease_seconds))
    )
    await session.flush()
    return task


async def owned(session: AsyncSession, task_id: UUID, token: UUID) -> BackgroundTask:
    task = await session.scalar(
        select(BackgroundTask)
        .where(
            BackgroundTask.task_id == task_id,
            BackgroundTask.state == TaskState.RUNNING,
            BackgroundTask.lease_token == token,
            BackgroundTask.lease_until > func.now(),
        )
        .with_for_update()
    )
    if task is None:
        raise LostLease("task_lease_lost")
    return task


async def heartbeat(
    session: AsyncSession, task_id: UUID, token: UUID, lease_seconds: int
) -> bool:
    result = await session.execute(
        update(BackgroundTask)
        .where(
            BackgroundTask.task_id == task_id,
            BackgroundTask.state == TaskState.RUNNING,
            BackgroundTask.lease_token == token,
            BackgroundTask.lease_until > func.now(),
        )
        .values(lease_until=func.now() + timedelta(seconds=lease_seconds))
    )
    return result.rowcount == 1


async def finish(
    session: AsyncSession,
    task_id: UUID,
    token: UUID,
    state: TaskState,
    *,
    result: dict | None = None,
    code: str | None = None,
    delay: float = 0,
    apply: Callable[[AsyncSession], Awaitable[None]] | None = None,
) -> None:
    if state not in {
        TaskState.SUCCEEDED,
        TaskState.RETRY_WAIT,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.NEEDS_REVIEW,
    }:
        raise ValueError("invalid finish state")
    with session.no_autoflush:
        task = await owned(session, task_id, token)
    if apply is not None:
        await apply(session)
    if task.queue == TaskQueue.PUBLICATION and state == TaskState.NEEDS_REVIEW:
        await mark_publication_unknown(session, task)
    task.state, task.result, task.error_code = state, result, code
    task.lease_token = task.lease_until = None
    if state == TaskState.RETRY_WAIT:
        task.available_at = await session.scalar(
            select(func.now() + timedelta(seconds=delay))
        )
    else:
        task.finished_at = await session.scalar(select(func.now()))
    await session.flush()


async def recover_expired(session: AsyncSession, *, limit: int = 100) -> int:
    tasks = list(
        await session.scalars(
            select(BackgroundTask)
            .where(
                BackgroundTask.state == TaskState.RUNNING,
                BackgroundTask.lease_until <= func.now(),
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for task in tasks:
        if task.queue == TaskQueue.PUBLICATION:
            task.state = TaskState.NEEDS_REVIEW
        elif task.attempts >= task.max_attempts:
            task.state = TaskState.FAILED
        else:
            task.state = TaskState.RETRY_WAIT
            task.available_at = await session.scalar(
                select(
                    func.now()
                    + timedelta(seconds=POLICIES[task.queue].delay(task.attempts))
                )
            )
        if task.queue == TaskQueue.COLLECTION:
            run_ids = select(CollectionRun.collection_run_id).where(
                CollectionRun.background_task_id == task.task_id
            )
            await session.execute(
                update(CollectionSourceRun)
                .where(
                    CollectionSourceRun.collection_run_id.in_(run_ids),
                    CollectionSourceRun.status == CollectionSourceRunStatus.RUNNING,
                )
                .values(
                    status=CollectionSourceRunStatus.INTERRUPTED,
                    finished_at=func.now(),
                    error_message="Исполнитель фоновой задачи прерван",
                )
            )
            await session.execute(
                update(CollectionRun)
                .where(
                    CollectionRun.background_task_id == task.task_id,
                    CollectionRun.status == CollectionRunStatus.RUNNING,
                )
                .values(
                    status=CollectionRunStatus.INTERRUPTED,
                    finished_at=func.now(),
                    error_message="Исполнитель фоновой задачи прерван",
                )
            )
        if task.queue == TaskQueue.PUBLICATION:
            attempt = await latest_publication_attempt(session, task)
            if attempt is None:
                # No Sending reservation was committed, so no message was sent.
                task.state = (
                    TaskState.FAILED
                    if task.attempts >= task.max_attempts
                    else TaskState.RETRY_WAIT
                )
                task.available_at = await session.scalar(
                    select(
                        func.now()
                        + timedelta(seconds=POLICIES[task.queue].delay(task.attempts))
                    )
                )
            elif attempt.status == PublicationAttemptStatus.CONFIRMED:
                task.state = TaskState.SUCCEEDED
                task.result = {"queue_item_id": task.subject_id, "recovered": True}
            elif attempt.status == PublicationAttemptStatus.SENDING:
                await mark_publication_unknown(session, task)
            elif attempt.status == PublicationAttemptStatus.FAILED:
                task.state = TaskState.FAILED
        task.error_code = "worker_lease_expired"
        task.lease_token = task.lease_until = None
        if task.state != TaskState.RETRY_WAIT:
            task.finished_at = await session.scalar(select(func.now()))
    await session.flush()
    return len(tasks)


async def latest_publication_attempt(session, task):
    return await session.scalar(
        select(PublicationAttempt)
        .where(PublicationAttempt.background_task_id == task.task_id)
        .order_by(PublicationAttempt.publication_attempt_id.desc())
        .with_for_update()
        .limit(1)
    )


async def mark_publication_unknown(session, task):
    # Reconcile only this task's reservation, also when timeout cancels a sender.
    attempt = await latest_publication_attempt(session, task)
    if attempt is None or attempt.status != PublicationAttemptStatus.SENDING:
        return
    attempt.status = PublicationAttemptStatus.UNKNOWN
    attempt.finished_at = await session.scalar(select(func.now()))
    attempt.error_type = "WorkerInterrupted"
    attempt.error_message = "Результат отправки требует проверки"
    await session.execute(
        update(Publication)
        .where(
            Publication.publication_id == attempt.publication_id,
            Publication.status == PublicationStatus.PUBLISHING,
        )
        .values(
            status=PublicationStatus.UNKNOWN,
            error_message="Результат отправки требует проверки",
        )
    )
    await session.execute(
        update(QueueItem)
        .where(
            QueueItem.queue_item_id == task.subject_id,
            QueueItem.status != QueueItemStatus.PUBLISHED,
        )
        .values(
            status=QueueItemStatus.PUBLICATION_UNKNOWN,
            error_message="Результат отправки требует проверки",
        )
    )
