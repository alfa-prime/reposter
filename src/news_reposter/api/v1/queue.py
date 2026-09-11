import base64
import binascii
import os
from pathlib import Path as FilePath
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.db.models import AttachmentType, QueueItemStatus
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
    QueueMediaUpload,
)

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=API_KEY_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]

MEDIA_ROOT = FilePath(os.getenv("MEDIA_ROOT", "/app/data/media"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


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


def media_directory(queue_item_id: int) -> FilePath:
    return MEDIA_ROOT / str(queue_item_id)


def uploaded_photos(queue_item_id: int, start_position: int) -> list[dict[str, Any]]:
    directory = media_directory(queue_item_id)
    if not directory.exists():
        return []

    photos: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime)):
        if not path.is_file():
            continue
        photos.append(
            {
                "attachment_id": -(index + 1),
                "external_attachment_id": f"upload:{path.name}",
                "source_url": f"/api/v1/queue/{queue_item_id}/media/{path.name}",
                "position": start_position + index,
                "kind": "uploaded",
                "media_id": path.name,
            }
        )
    return photos


def queue_item_response(item: Any) -> QueueItemRead:
    """Добавляет к элементу очереди исходник, фото, пользовательские медиа и цель."""

    base = QueueItemRead.model_validate(item).model_dump()
    post = getattr(item, "post", None)
    target = getattr(item, "target", None)
    photos: list[dict[str, Any]] = []

    if post is not None:
        for attachment in getattr(post, "attachments", []):
            if attachment.attachment_type != AttachmentType.PHOTO or not attachment.source_url:
                continue
            photos.append(
                {
                    "attachment_id": attachment.attachment_id,
                    "external_attachment_id": attachment.external_attachment_id,
                    "source_url": attachment.source_url,
                    "position": attachment.position,
                    "kind": "source",
                    "media_id": None,
                }
            )

        base.update(
            {
                "original_text": post.original_text,
                "source_url": post.source_url,
                "source_published_at": post.source_published_at,
            }
        )

    photos.extend(uploaded_photos(item.queue_item_id, len(photos)))
    base["photos"] = photos

    if target is not None:
        base.update(
            {
                "target_name": target.name,
                "target_platform": target.platform,
                "target_url": target.url,
            }
        )

    return QueueItemRead.model_validate(base)


@router.post(
    "",
    response_model=QueueItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить пост в очередь",
    description=(
        "Создаёт редакционный элемент для конкретной пары исходный пост + "
        "целевой канал. Один пост нельзя дважды добавить в один и тот же канал."
    ),
    response_description="Созданный элемент очереди с исходным текстом и фото",
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
    return queue_item_response(item)


@router.get(
    "",
    response_model=list[QueueItemRead],
    summary="Получить очередь постов",
    description=(
        "Возвращает редакционную очередь с фильтрами по целевому каналу, "
        "исходному посту, источнику и статусу. Для каждого элемента возвращает "
        "исходный текст, ссылку на пост, фотографии и данные целевого канала."
    ),
    response_description="Список элементов очереди с исходными постами и фото",
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
    return [queue_item_response(item) for item in items]


@router.get(
    "/{queue_item_id}",
    response_model=QueueItemRead,
    summary="Получить элемент очереди",
    description=(
        "Возвращает один редакционный элемент очереди вместе с исходным текстом, "
        "ссылкой на VK, фотографиями и данными целевого канала."
    ),
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
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/media",
    response_model=QueueItemRead,
    summary="Добавить фото к публикации",
    description=(
        "Сохраняет пользовательское JPEG, PNG или WebP изображение для конкретного "
        "элемента очереди. Максимальный размер одного файла — 10 МБ."
    ),
    responses={404: {"description": "Элемент очереди не найден"}, 413: {"description": "Файл слишком большой"}},
)
async def upload_queue_media(
    queue_item_id: Annotated[int, Path(gt=0, description="Идентификатор элемента очереди")],
    data: QueueMediaUpload,
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()

    extension = ALLOWED_IMAGE_TYPES.get(data.content_type.lower())
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются только JPEG, PNG и WebP",
        )

    try:
        content = base64.b64decode(data.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Некорректные данные файла") from exc

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 10 МБ")
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")

    directory = media_directory(queue_item_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    (directory / filename).write_bytes(content)
    return queue_item_response(item)


@router.get(
    "/{queue_item_id}/media/{media_id}",
    summary="Получить загруженное фото",
    responses={404: {"description": "Файл не найден"}},
)
async def get_queue_media(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=100)],
    _api_key: ApiKeyDep,
) -> FileResponse:
    safe_name = FilePath(media_id).name
    if safe_name != media_id:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")
    path = media_directory(queue_item_id) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path)


@router.delete(
    "/{queue_item_id}/media/{media_id}",
    response_model=QueueItemRead,
    summary="Удалить загруженное фото",
    responses={404: {"description": "Элемент очереди или файл не найден"}},
)
async def delete_queue_media(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=100)],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await repository.get(queue_item_id)
    if item is None:
        raise not_found_error()

    safe_name = FilePath(media_id).name
    if safe_name != media_id:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")
    path = media_directory(queue_item_id) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    path.unlink()
    return queue_item_response(item)


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
    return queue_item_response(item)


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
    return queue_item_response(item)


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
    return queue_item_response(item)


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
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/reopen",
    response_model=QueueItemRead,
    summary="Вернуть пост в работу",
    description=(
        "Возвращает пост в статус pending для повторного редактирования. "
        "Можно использовать после модерации, одобрения или планирования."
    ),
    responses={404: {"description": "Элемент очереди не найден"}, 409: {"description": "Недопустимый переход статуса"}},
)
async def reopen_queue_item(
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
        {
            QueueItemStatus.AWAITING_MODERATION,
            QueueItemStatus.APPROVED,
            QueueItemStatus.REJECTED,
            QueueItemStatus.SCHEDULED,
        },
    )
    item = await repository.set_status(item, QueueItemStatus.PENDING)
    return queue_item_response(item)


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
    return queue_item_response(item)


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

    directory = media_directory(queue_item_id)
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file():
                path.unlink()
        directory.rmdir()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
