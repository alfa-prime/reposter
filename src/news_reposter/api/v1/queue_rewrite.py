from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.api.v1.queue import conflict_error, not_found_error, queue_item_response
from news_reposter.db.models import QueueItemStatus
from news_reposter.db.session import get_db_session
from news_reposter.llm import LLMProviderError
from news_reposter.llm.factory import get_llm_provider
from news_reposter.repositories.queue_item import QueueItemRepository
from news_reposter.schemas.queue_item import QueueItemRead, QueueItemUpdate
from news_reposter.services.rewrite import RewriteService, RewriteServiceError

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=API_KEY_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]

REWRITE_ALLOWED_STATUSES = {
    QueueItemStatus.PENDING,
    QueueItemStatus.REWRITING,
    QueueItemStatus.REJECTED,
}


@router.post(
    "/{queue_item_id}/rewrite",
    response_model=QueueItemRead,
    summary="Переписать пост с помощью ИИ",
    description=(
        "Берёт исходный текст поста, выбирает индивидуальный промпт целевого канала "
        "или общий промпт приложения и отправляет запрос настроенному LLM-провайдеру. "
        "Исходный текст не изменяется. Успешный результат сохраняется в rewritten_text, "
        "а публикация остаётся в статусе rewriting для проверки редактором."
    ),
    responses={
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Рерайт недоступен для текущего состояния или нет исходного текста"},
        502: {"description": "LLM-провайдер не выполнил запрос"},
        503: {"description": "LLM-провайдер не настроен"},
    },
)
async def rewrite_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    if item.status not in REWRITE_ALLOWED_STATUSES:
        raise conflict_error(f"Рерайт недоступен для статуса {item.status.value}")

    previous_status = item.status
    try:
        provider = get_llm_provider()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    service = RewriteService(provider)
    try:
        service.context_for(item)
    except RewriteServiceError as exc:
        raise conflict_error(str(exc)) from exc

    if item.status != QueueItemStatus.REWRITING:
        item = await repository.set_status(item, QueueItemStatus.REWRITING)

    try:
        result = await service.rewrite(item)
    except (LLMProviderError, RewriteServiceError) as exc:
        current = await repository.get(queue_item_id)
        if current is not None and previous_status != QueueItemStatus.REWRITING:
            await repository.set_status(current, previous_status)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось переписать пост: {exc}",
        ) from exc

    item = await repository.update(
        item,
        QueueItemUpdate(rewritten_text=result.text),
    )
    return queue_item_response(item)
