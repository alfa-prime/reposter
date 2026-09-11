from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.db.models import QueueItemStatus
from news_reposter.db.session import get_db_session
from news_reposter.repositories.queue_item import (
    QueueItemAlreadyExistsError,
    QueueItemRepository,
)
from news_reposter.schemas.queue_item import (
    QueueItemCreate,
    QueueItemRead,
    QueueItemSchedule,
    QueueItemUpdate,
)

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=API_KEY_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]


def not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Элемент очереди не найден",
    )


def conflict_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def ensure_status(item_status: QueueItemStatus, allowed: set[QueueItemStatus]) -> None:
    if item_status not in allowed:
        allowed_text = ", ".join(sorted(value.value for value in allowed))
        raise conflict_error(
            f"Операция недоступна для статуса {item_status.value}; "
            f"допустимые статусы: {allowed_text}"
        )


@router.post(
    "",
    response_model=QueueItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить пост в очередь",
    description=(
        "Создаёт редакционный элемент для конкретной пары исходный пост + "
        "целевой канал. Один пост нельзя дважды добавить в один и тот же канал."
    ),
    response_description="Созданный элемент очереди",
    responses={
        404: {"description": "Исходный пост или целевой канал не найдены"},
        409: {"description": "Пост уже находится в очереди этого канала"},
    },
)
async def create_queue_item(
    data: QueueItemCreate,
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    if not await repository.post_exists(data.post_id):
        raise HTTPException(status_code=404, detail="Исходный пост не найден")
    if not await repository.target_exists(data.target_id):
        raise HTTPException(status_code=404, detail="Целевой канал не найден")
    try:
        item = await repository.create(data)
    except QueueItemAlreadyExistsError as exc:
        raise conflict_error("Пост уже находится в очереди этого канала") from exc
    return QueueItemRead.model_validate(item)


@router.get(
    "",
    response_model=list[QueueItemRead],
    summary="Получить очередь постов",
    description=(
        "Возвращает редакционную очередь с фильтрами по целевому каналу, "
        "исходному посту, источнику и статусу."
    ),
    response_description="Список элементов очереди",
)
async def list_queue_items(
    session: Session,
    _api_key: ApiKeyDep,
    offset: Annotated[int, Query(ge=0, description="Сколько записей пропустить")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Максимум записей")] = 50,
    target_id: Annotated[int | None, Query(gt=0, description="Фильтр по каналу")] = None,
    post_id: Annotated[int | None, Query(gt=0, description="Фильтр по посту")] = None,
    source_id: Annotated[int | None, Query(gt=0, description="Фильтр по источнику")] = None,
    queue_status: Annotated[
        QueueItemStatus | None,
        Query(alias="status", description="Фильтр по редакционному статусу"),
    ] = None,
) -> list[QueueItemRead]:
    items = await QueueItemRepository(session).list(
        offset=offset,
        limit=limit,
        target_id=target_id,
        post_id=post_id,
        source_id=source_id,
        status=queue_status,
    )
    return [QueueItemRead.model_validate(item) for item in items]


@router.get(
    "/{queue_item_id}",
    response_model=QueueItemRead,
    summary="Получить элемент очереди",
    description="Возвращает один редакционный элемент очереди по его ID.",
    responses={404: {"description": "Элемент очереди не найден"}},
)
async def get_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    item = await QueueItemRepository(session).get(queue_item_id)
    if item is None:
        raise not_found_error()
    return QueueItemRead.model_validate(item)


@router.patch(
    "/{queue_item_id}",
    response_model=QueueItemRead,
    summary="Изменить текст элемента очереди",
    description=(
        "Редактирует подготовленный текст. Статус через PATCH не меняется: "
        "для модерации используются отдельные операции."
    ),
    responses={404: {"description": "Элемент очереди не найден"}},
)
async def update_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    data: QueueItemUpdate,
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    item = await repository.update(item, data)
    return QueueItemRead.model_validate(item)


@router.post(
    "/{queue_item_id}/submit",
    response_model=QueueItemRead,
    summary="Отправить пост на модерацию",
    description="Переводит подготовленный пост в статус awaiting_moderation.",
    responses={404: {"description": "Элемент очереди не найден"}, 409: {"description": "Недопустимый переход статуса"}},
)
async def submit_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    ensure_status(
        item.status,
        {QueueItemStatus.PENDING, QueueItemStatus.REWRITING, QueueItemStatus.REJECTED},
    )
    if not item.rewritten_text or not item.rewritten_text.strip():
        raise conflict_error("Перед отправкой на модерацию нужен подготовленный текст")
    item = await repository.set_status(item, QueueItemStatus.AWAITING_MODERATION)
    return QueueItemRead.model_validate(item)


@router.post(
    "/{queue_item_id}/approve",
    response_model=QueueItemRead,
    summary="Одобрить пост",
    description="Одобряет пост, находящийся на модерации.",
    responses={404: {"description": "Элемент очереди не найден"}, 409: {"description": "Недопустимый переход статуса"}},
)
async def approve_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    ensure_status(item.status, {QueueItemStatus.AWAITING_MODERATION})
    item = await repository.set_status(item, QueueItemStatus.APPROVED)
    return QueueItemRead.model_validate(item)


@router.post(
    "/{queue_item_id}/reject",
    response_model=QueueItemRead,
    summary="Отклонить пост",
    description="Отклоняет пост, находящийся на модерации.",
    responses={404: {"description": "Элемент очереди не найден"}, 409: {"description": "Недопустимый переход статуса"}},
)
async def reject_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    ensure_status(item.status, {QueueItemStatus.AWAITING_MODERATION})
    item = await repository.set_status(item, QueueItemStatus.REJECTED)
    return QueueItemRead.model_validate(item)


@router.post(
    "/{queue_item_id}/schedule",
    response_model=QueueItemRead,
    summary="Запланировать публикацию",
    description="Назначает время публикации для одобренного поста.",
    responses={404: {"description": "Элемент очереди не найден"}, 409: {"description": "Недопустимый переход статуса"}},
)
async def schedule_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    data: QueueItemSchedule,
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    ensure_status(item.status, {QueueItemStatus.APPROVED})
    item = await repository.set_status(
        item,
        QueueItemStatus.SCHEDULED,
        scheduled_at=data.scheduled_at,
    )
    return QueueItemRead.model_validate(item)


@router.delete(
    "/{queue_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить элемент очереди",
    description="Удаляет редакционный элемент очереди до технической публикации.",
    responses={404: {"description": "Элемент очереди не найден"}},
)
async def delete_queue_item(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    session: Session,
    _api_key: ApiKeyDep,
) -> Response:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()
    await repository.delete(item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
