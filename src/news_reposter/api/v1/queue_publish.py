from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    HttpClientDep,
    SameOriginDep,
)
from news_reposter.api.v1.queue import queue_item_response
from news_reposter.api.v1.queue_permissions import (
    QueuePublishDep,
    get_accessible_queue_item,
)
from news_reposter.config import get_settings
from news_reposter.db.models import (
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItemStatus,
)
from news_reposter.db.session import get_db_session
from news_reposter.integrations.max import MAXAPIError, MAXClient
from news_reposter.repositories.queue_item import QueueItemRepository
from news_reposter.schemas.queue_item import (
    MarkPublishedRequest,
    PublicationRecoveryResult,
    QueueItemRead,
    RetryPublicationRequest,
)
from news_reposter.services.audit import record_editorial_event
from news_reposter.services.publisher import (
    PublicationError,
    PublicationUnknownError,
    publish_queue_item,
)

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=PERMISSION_CSRF_AUTH_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/{queue_item_id}/publish-now",
    response_model=QueueItemRead,
    summary="Опубликовать пост сейчас",
    description=(
        "Отправляет одобренный или запланированный пост в целевой канал MAX. "
        "Учитывает подпись, выбранные фотографии и загруженные вручную видео."
    ),
    responses={
        409: {"description": "Пост нельзя опубликовать в текущем состоянии"},
        502: {"description": "MAX не принял публикацию"},
    },
)
async def publish_now(
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    auth: QueuePublishDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
    http_client: HttpClientDep,
) -> QueueItemRead:
    accessible_item = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    if accessible_item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")
    previous_status = accessible_item.status.value
    try:
        item = await publish_queue_item(
            session,
            queue_item_id,
            http_client,
            commit_success=False,
            actor_user_id=auth.user.user_id,
            trigger="manual",
        )
    except PublicationUnknownError as exc:
        item = await get_accessible_queue_item(
            QueueItemRepository(session), queue_item_id, auth
        )
        assert item is not None
        await record_editorial_event(
            session,
            actor_user_id=auth.user.user_id,
            item=item,
            action="editorial.publication_unknown",
            details={"previous_status": previous_status, "error": str(exc)},
        )
        return queue_item_response(item)
    except PublicationError as exc:
        detail = str(exc)
        upstream_markers = (
            "MAX",
            "загруз",
            "сертифик",
            "token",
        )
        code = (
            status.HTTP_502_BAD_GATEWAY
            if any(marker.lower() in detail.lower() for marker in upstream_markers)
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=detail) from exc

    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.published",
        details={"previous_status": previous_status, "status": item.status.value},
    )
    return queue_item_response(item)


def _unknown_attempt(item):
    publication = item.publication
    if publication is None or publication.status != PublicationStatus.UNKNOWN:
        raise HTTPException(
            status_code=409, detail="У публикации нет неопределённой попытки"
        )
    attempt = next(
        (
            row
            for row in publication.attempt_history
            if row.status == PublicationAttemptStatus.UNKNOWN
        ),
        None,
    )
    if attempt is None:
        raise HTTPException(
            status_code=409, detail="История неопределённой попытки не найдена"
        )
    return publication, attempt


def _messages(payload: dict) -> list[dict]:
    rows = payload.get("messages", [])
    return (
        [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    )


def _message_text(message: dict) -> str:
    body = message.get("body")
    return str(body.get("text", "")).strip() if isinstance(body, dict) else ""


def _message_id(message: dict) -> str | None:
    body = message.get("body")
    value = body.get("mid") if isinstance(body, dict) else None
    return str(value) if value is not None else None


async def _recovery_item(session: AsyncSession, queue_item_id: int, auth):
    item = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")
    if item.status != QueueItemStatus.PUBLICATION_UNKNOWN:
        raise HTTPException(
            status_code=409, detail="Материал не требует проверки публикации"
        )
    return item


@router.post(
    "/{queue_item_id}/check-publication", response_model=PublicationRecoveryResult
)
async def check_publication(
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    auth: QueuePublishDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
    http_client: HttpClientDep,
) -> PublicationRecoveryResult:
    item = await _recovery_item(session, queue_item_id, auth)
    publication, attempt = _unknown_attempt(item)
    settings = get_settings()
    try:
        chat_id = int(item.target.external_id)
        client = MAXClient(
            access_token=settings.max_access_token,
            http_client=http_client,
            chat_id=chat_id,
            api_url=settings.max_api_url,
        )
        start = attempt.started_at - timedelta(minutes=2)
        end = (attempt.finished_at or datetime.now(UTC)) + timedelta(minutes=10)
        payload = await client.get_messages(
            from_timestamp=int(start.timestamp() * 1000),
            to_timestamp=int(end.timestamp() * 1000),
            count=100,
        )
    except (ValueError, MAXAPIError) as exc:
        raise HTTPException(
            status_code=502, detail=f"Не удалось проверить канал MAX: {exc}"
        ) from exc

    matches = [
        message
        for message in _messages(payload)
        if _message_text(message) == attempt.prepared_text.strip()
    ]
    attempt.check_count += 1
    attempt.last_checked_at = datetime.now(UTC)
    if len(matches) == 1:
        mid = _message_id(matches[0])
        publication.status = PublicationStatus.PUBLISHED
        publication.external_message_id = mid
        publication.published_at = datetime.now(UTC)
        publication.error_message = None
        attempt.status = PublicationAttemptStatus.CONFIRMED
        attempt.external_message_id = mid
        attempt.finished_at = attempt.finished_at or datetime.now(UTC)
        item.status = QueueItemStatus.PUBLISHED
        item.error_message = None
        outcome = "found"
        message = "Публикация найдена в MAX и подтверждена автоматически."
        action = "editorial.publication_reconciled"
    elif len(matches) > 1:
        outcome = "ambiguous"
        message = "Найдено несколько похожих сообщений. Нужна ручная проверка канала."
        action = "editorial.publication_checked"
    else:
        outcome = "not_found"
        message = (
            "Точное совпадение не найдено. Проверьте канал вручную перед повтором."
        )
        action = "editorial.publication_checked"
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action=action,
        details={
            "outcome": outcome,
            "matches": len(matches),
            "check_count": attempt.check_count,
        },
    )
    refreshed = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    assert refreshed is not None
    return PublicationRecoveryResult(
        item=queue_item_response(refreshed), outcome=outcome, message=message
    )


@router.post("/{queue_item_id}/mark-published", response_model=QueueItemRead)
async def mark_published(
    data: MarkPublishedRequest,
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    auth: QueuePublishDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    item = await _recovery_item(session, queue_item_id, auth)
    publication, attempt = _unknown_attempt(item)
    publication.status = PublicationStatus.PUBLISHED
    publication.publication_url = data.publication_url
    publication.external_message_id = data.external_message_id
    publication.published_at = datetime.now(UTC)
    publication.error_message = None
    attempt.status = PublicationAttemptStatus.CONFIRMED
    attempt.publication_url = data.publication_url
    attempt.external_message_id = data.external_message_id
    item.status = QueueItemStatus.PUBLISHED
    item.error_message = None
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.publication_marked_manually",
        details={"comment": data.comment, "publication_url": data.publication_url},
    )
    refreshed = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    assert refreshed is not None
    return queue_item_response(refreshed)


@router.post("/{queue_item_id}/retry-publication", response_model=QueueItemRead)
async def retry_publication(
    data: RetryPublicationRequest,
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    auth: QueuePublishDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
    http_client: HttpClientDep,
) -> QueueItemRead:
    item = await _recovery_item(session, queue_item_id, auth)
    _, attempt = _unknown_attempt(item)
    if (
        not data.checked_channel
        or not data.accept_duplicate_risk
        or attempt.check_count < 1
    ):
        raise HTTPException(
            status_code=409,
            detail="Сначала выполните проверку MAX и подтвердите риск дубликата",
        )
    try:
        published = await publish_queue_item(
            session,
            queue_item_id,
            http_client,
            commit_success=False,
            actor_user_id=auth.user.user_id,
            trigger="manual_retry",
            allow_unknown_retry=True,
        )
    except PublicationUnknownError:
        published = await _recovery_item(session, queue_item_id, auth)
    except PublicationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=published,
        action="editorial.publication_retried",
        details={"accepted_duplicate_risk": True},
    )
    return queue_item_response(published)


@router.post("/{queue_item_id}/return-to-work", response_model=QueueItemRead)
async def return_to_work(
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    auth: QueuePublishDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    item = await _recovery_item(session, queue_item_id, auth)
    publication, attempt = _unknown_attempt(item)
    if attempt.check_count < 1:
        raise HTTPException(
            status_code=409, detail="Сначала проверьте публикацию в MAX"
        )
    publication.status = PublicationStatus.FAILED
    publication.error_message = (
        "Возвращено сотрудником в редакционную работу после проверки MAX"
    )
    item.status = QueueItemStatus.PENDING
    item.error_message = None
    item.scheduled_at = None
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.publication_returned_to_work",
        details={"attempt_number": attempt.attempt_number},
    )
    refreshed = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    assert refreshed is not None
    return queue_item_response(refreshed)
