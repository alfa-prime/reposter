"""Opt-in 202 endpoints; existing synchronous API contracts stay available."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    SameOriginDep,
    require_permission,
)
from news_reposter.api.v1.background_tasks import check_task_access
from news_reposter.api.v1.queue_permissions import (
    QueuePublishDep,
    QueueRewriteDep,
    can_access_target,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.background.contracts import (
    ActiveTaskConflict,
    IdempotencyConflict,
    TaskQueue,
)
from news_reposter.background.intents import (
    enqueue_collection,
    publication_snapshot,
    rewrite_snapshot,
)
from news_reposter.background.store import enqueue
from news_reposter.config import get_settings
from news_reposter.db.models import (
    BackgroundTask,
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItemStatus,
)
from news_reposter.db.session import get_db_session
from news_reposter.schemas.background_task import (
    PublicationRetrySubmission,
    TaskRead,
    TaskSubmission,
)
from news_reposter.services.publisher import _loaded_item
from news_reposter.services.rewrite import RewriteServiceError

router = APIRouter(tags=["Система"], responses=PERMISSION_CSRF_AUTH_RESPONSES)
Session = Annotated[AsyncSession, Depends(get_db_session)]
CollectionDep = Annotated[
    AuthContext, Depends(require_permission(PermissionCode.COLLECTION_RUN))
]


def enabled():
    if not get_settings().background_tasks_enabled:
        raise HTTPException(
            status_code=503, detail="Фоновое исполнение ещё не включено"
        )


async def submit_material(session, auth, data, item_id, queue):
    enabled()
    key = f"{queue.value}:{auth.user.user_id}:{data.idempotency_key}"
    existing = await session.scalar(
        select(BackgroundTask).where(BackgroundTask.idempotency_key == key)
    )
    if existing:
        if existing.subject_id != item_id:
            raise HTTPException(
                status_code=409, detail="Ключ уже использован для другого материала"
            )
        check_task_access(existing, auth)
        return TaskRead.model_validate(existing)
    item = await _loaded_item(session, item_id, for_update=True)
    if item is None or not can_access_target(auth, item.target_id):
        raise HTTPException(status_code=404, detail="Материал не найден")
    allowed = (
        {QueueItemStatus.PENDING, QueueItemStatus.REWRITING, QueueItemStatus.REJECTED}
        if queue == TaskQueue.REWRITE
        else {
            QueueItemStatus.APPROVED,
            QueueItemStatus.FAILED,
            QueueItemStatus.SCHEDULED,
        }
    )
    if item.status not in allowed:
        raise HTTPException(
            status_code=409, detail="Операция недоступна в текущем состоянии материала"
        )
    try:
        snapshot = (
            rewrite_snapshot(item)
            if queue == TaskQueue.REWRITE
            else publication_snapshot(item)
        )
        task = await enqueue(
            session,
            queue,
            key,
            {
                "snapshot": snapshot,
                **({"trigger": "manual"} if queue == TaskQueue.PUBLICATION else {}),
            },
            actor_user_id=auth.user.user_id,
            subject_id=item_id,
            target_id=item.target_id,
        )
    except (ActiveTaskConflict, IdempotencyConflict) as exc:
        raise HTTPException(
            status_code=409,
            detail="Задача уже существует или ключ использован повторно",
        ) from exc
    except (ValueError, RewriteServiceError) as exc:
        raise HTTPException(
            status_code=409, detail="Материал нельзя подготовить к операции"
        ) from exc
    await session.commit()
    return TaskRead.model_validate(task)


@router.post(
    "/queue/{queue_item_id}/rewrite-task",
    status_code=202,
    response_model=TaskRead,
    summary="Поставить рерайт в фоновую очередь",
)
async def rewrite_task(
    queue_item_id: int,
    data: TaskSubmission,
    auth: QueueRewriteDep,
    session: Session,
    _csrf: CsrfAuthContextDep,
    _origin: SameOriginDep,
):
    return await submit_material(session, auth, data, queue_item_id, TaskQueue.REWRITE)


@router.post(
    "/queue/{queue_item_id}/publish-task",
    status_code=202,
    response_model=TaskRead,
    summary="Поставить публикацию в фоновую очередь",
)
async def publish_task(
    queue_item_id: int,
    data: TaskSubmission,
    auth: QueuePublishDep,
    session: Session,
    _csrf: CsrfAuthContextDep,
    _origin: SameOriginDep,
):
    return await submit_material(
        session, auth, data, queue_item_id, TaskQueue.PUBLICATION
    )


@router.post(
    "/queue/{queue_item_id}/retry-publication-task",
    status_code=202,
    response_model=TaskRead,
    summary="Повторить проверенную публикацию в фоновой очереди",
)
async def retry_publication_task(
    queue_item_id: int,
    data: PublicationRetrySubmission,
    auth: QueuePublishDep,
    session: Session,
    _csrf: CsrfAuthContextDep,
    _origin: SameOriginDep,
):
    enabled()
    key = f"publication-retry:{auth.user.user_id}:{data.idempotency_key}"
    existing = await session.scalar(
        select(BackgroundTask).where(BackgroundTask.idempotency_key == key)
    )
    if existing:
        if existing.subject_id != queue_item_id:
            raise HTTPException(
                status_code=409, detail="Ключ использован для другого материала"
            )
        check_task_access(existing, auth)
        return TaskRead.model_validate(existing)

    item = await _loaded_item(session, queue_item_id, for_update=True)
    if item is None or not can_access_target(auth, item.target_id):
        raise HTTPException(status_code=404, detail="Материал не найден")
    publication = item.publication
    attempt = (
        max(
            publication.attempt_history,
            key=lambda row: row.attempt_number,
            default=None,
        )
        if publication is not None
        else None
    )
    if (
        item.status != QueueItemStatus.PUBLICATION_UNKNOWN
        or publication is None
        or publication.status != PublicationStatus.UNKNOWN
        or attempt is None
        or attempt.status != PublicationAttemptStatus.UNKNOWN
        or attempt.check_count < 1
    ):
        raise HTTPException(
            status_code=409,
            detail="Сначала проверьте публикацию в MAX",
        )
    try:
        task = await enqueue(
            session,
            TaskQueue.PUBLICATION,
            key,
            {
                "snapshot": publication_snapshot(item),
                "trigger": "manual_retry",
                "accept_duplicate_risk": True,
            },
            actor_user_id=auth.user.user_id,
            subject_id=queue_item_id,
            target_id=item.target_id,
        )
    except (ActiveTaskConflict, IdempotencyConflict) as exc:
        raise HTTPException(
            status_code=409, detail="Задача публикации уже существует"
        ) from exc
    await session.commit()
    return TaskRead.model_validate(task)


@router.post(
    "/system/collection/tasks",
    status_code=202,
    response_model=TaskRead,
    summary="Поставить сбор в фоновую очередь",
)
async def collection_task(
    data: TaskSubmission,
    auth: CollectionDep,
    session: Session,
    _csrf: CsrfAuthContextDep,
    _origin: SameOriginDep,
):
    enabled()
    try:
        task = await enqueue_collection(
            session,
            f"collection:{auth.user.user_id}:{data.idempotency_key}",
            actor_user_id=auth.user.user_id,
            trigger="manual",
        )
    except (ActiveTaskConflict, IdempotencyConflict) as exc:
        raise HTTPException(
            status_code=409, detail="Сбор уже поставлен в очередь"
        ) from exc
    await session.commit()
    return TaskRead.model_validate(task)
