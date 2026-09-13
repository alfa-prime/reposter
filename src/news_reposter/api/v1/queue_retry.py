from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.api.v1.queue import queue_item_response
from news_reposter.db.models import QueueItemStatus
from news_reposter.db.session import get_db_session
from news_reposter.repositories.queue_item import QueueItemRepository
from news_reposter.schemas.queue_item import QueueItemRead

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=API_KEY_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/{queue_item_id}/prepare-retry",
    response_model=QueueItemRead,
    summary="Подготовить повтор публикации",
    description=(
        "Возвращает неудачную публикацию в согласованный статус, чтобы её можно "
        "было повторно отправить без новой модерации."
    ),
    responses={
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Повтор доступен только после ошибки публикации"},
    },
)
async def prepare_retry(
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")
    if item.status != QueueItemStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Повтор доступен только после ошибки публикации",
        )

    item.error_message = None
    item = await repository.set_status(item, QueueItemStatus.APPROVED)
    return queue_item_response(item)
