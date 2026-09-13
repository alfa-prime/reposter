from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.db.session import get_db_session
from news_reposter.schemas.queue_item import QueueItemRead
from news_reposter.services.publisher import PublicationError, publish_queue_item

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=API_KEY_RESPONSES,
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
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    try:
        item = await publish_queue_item(session, queue_item_id)
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

    # QueueItemRead умеет читать ORM-объект. Расширенные поля исходника/канала
    # фронтенд получит при следующем обычном GET /queue, статус обновится сразу.
    return QueueItemRead.model_validate(item)
