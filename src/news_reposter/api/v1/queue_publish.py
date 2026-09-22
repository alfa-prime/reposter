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
from news_reposter.api.v1.queue_permissions import QueuePublishDep
from news_reposter.db.session import get_db_session
from news_reposter.schemas.queue_item import QueueItemRead
from news_reposter.services.publisher import PublicationError, publish_queue_item

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
    _auth: QueuePublishDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
    http_client: HttpClientDep,
) -> QueueItemRead:
    try:
        item = await publish_queue_item(session, queue_item_id, http_client)
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

    return queue_item_response(item)
