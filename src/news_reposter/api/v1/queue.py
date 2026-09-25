import asyncio
from pathlib import Path as FilePath
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    SameOriginDep,
)
from news_reposter.api.v1.queue_media_state import load_state
from news_reposter.api.v1.queue_permissions import (
    QueueEditDep,
    QueueModerateDep,
    QueueReadDep,
    QueueScheduleDep,
    QueueSubmitDep,
    can_access_target,
    get_accessible_queue_item,
    target_scope,
)
from news_reposter.config import get_settings
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
    QueuePageRead,
)
from news_reposter.services.audit import record_editorial_event
from news_reposter.services.media_storage import (
    cleanup_queue_item_media,
    queue_item_directory,
)
from news_reposter.services.media_upload import (
    local_attachment_count,
    stream_file_to_disk,
    upload_metadata,
    upload_slot,
)
from news_reposter.services.media_validation import validate_image_content

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]

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


def ensure_not_reconciling(item_status: QueueItemStatus) -> None:
    if item_status == QueueItemStatus.PUBLICATION_UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Материал нельзя изменять, пока результат публикации не проверен",
        )


def media_directory(queue_item_id: int) -> FilePath:
    return queue_item_directory(queue_item_id)


def uploaded_photos(queue_item_id: int, start_position: int) -> list[dict[str, Any]]:
    directory = media_directory(queue_item_id)
    if not directory.exists():
        return []

    photos: list[dict[str, Any]] = []
    for index, path in enumerate(
        sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime)
    ):
        if not path.is_file() or path.name.startswith(".upload-"):
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
            if (
                attachment.attachment_type != AttachmentType.PHOTO
                or not attachment.source_url
            ):
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
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Исходный пост или целевой канал не найдены"},
        409: {"description": "Пост уже находится в очереди этого канала"},
    },
)
async def create_queue_item(
    data: QueueItemCreate,
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    if not await repository.post_exists(data.post_id):
        raise HTTPException(status_code=404, detail="Исходный пост не найден")
    if not await repository.target_exists(data.target_id):
        raise HTTPException(status_code=404, detail="Целевой канал не найден")
    if not can_access_target(auth, data.target_id):
        raise not_found_error()
    try:
        item = await repository.create(data, commit=False)
    except QueueItemAlreadyExistsError as exc:
        raise conflict_error("Пост уже находится в очереди этого канала") from exc
    await record_editorial_event(
        session, actor_user_id=auth.user.user_id, item=item, action="editorial.created"
    )
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
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_queue_items(
    session: Session,
    auth: QueueReadDep,
    offset: Annotated[int, Query(ge=0, description="Сколько записей пропустить")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Максимум записей")] = 50,
    target_id: Annotated[
        int | None, Query(gt=0, description="Фильтр по каналу")
    ] = None,
    post_id: Annotated[int | None, Query(gt=0, description="Фильтр по посту")] = None,
    source_id: Annotated[
        int | None, Query(gt=0, description="Фильтр по источнику")
    ] = None,
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
        **target_scope(auth),
    )
    return [queue_item_response(item) for item in items]


@router.get(
    "/page",
    response_model=QueuePageRead,
    summary="Получить страницу очереди постов",
    description=(
        "Возвращает только запрошенную страницу очереди, общее количество "
        "подходящих записей и счётчики всех статусов. Параметр status можно "
        "передать несколько раз."
    ),
    responses=PERMISSION_AUTH_RESPONSES,
)
async def get_queue_page(
    session: Session,
    auth: QueueReadDep,
    queue_statuses: Annotated[
        list[QueueItemStatus],
        Query(alias="status", description="Один или несколько статусов очереди"),
    ],
    offset: Annotated[int, Query(ge=0, description="Сколько записей пропустить")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Размер страницы")] = 20,
    target_id: Annotated[
        int | None, Query(gt=0, description="Фильтр по целевому каналу")
    ] = None,
) -> QueuePageRead:
    repository = QueueItemRepository(session)
    items = await repository.list_page(
        offset=offset,
        limit=limit,
        target_id=target_id,
        statuses=queue_statuses,
        **target_scope(auth),
    )
    counts = await repository.count_by_status(target_id=target_id, **target_scope(auth))
    return QueuePageRead(
        items=[queue_item_response(item) for item in items],
        total=sum(counts.get(queue_status, 0) for queue_status in queue_statuses),
        offset=offset,
        limit=limit,
        status_counts={
            queue_status.value: count for queue_status, count in counts.items()
        },
    )


@router.get(
    "/{queue_item_id}",
    response_model=QueueItemRead,
    summary="Получить элемент очереди",
    description=(
        "Возвращает один редакционный элемент очереди вместе с исходным текстом, "
        "ссылкой на VK, фотографиями и данными целевого канала."
    ),
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
    },
)
async def get_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    session: Session,
    auth: QueueReadDep,
) -> QueueItemRead:
    item = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
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
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
        413: {"description": "Файл слишком большой"},
    },
)
async def upload_queue_media(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    request: Request,
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_not_reconciling(item.status)

    _filename, content_type = upload_metadata(request)
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются только JPEG, PNG и WebP",
        )

    directory = media_directory(queue_item_id)
    settings = get_settings()
    async with upload_slot(queue_item_id):
        source_count = sum(key.startswith("source:") for key in load_state(item))
        stored_count = await asyncio.to_thread(local_attachment_count, directory)
        if source_count + stored_count >= settings.media_item_max_attachments:
            raise HTTPException(
                status_code=413,
                detail="В материале уже максимальное число вложений",
            )
        await stream_file_to_disk(
            request,
            directory=directory,
            filename_prefix="",
            extension=extension,
            max_bytes=settings.media_image_max_bytes,
            validate=validate_image_content,
            content_type=content_type,
        )
    return queue_item_response(item)


@router.get(
    "/{queue_item_id}/media/{media_id}",
    summary="Получить загруженное фото",
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Файл не найден"},
    },
)
async def get_queue_media(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=100)],
    session: Session,
    auth: QueueReadDep,
) -> FileResponse:
    item = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    if item is None:
        raise not_found_error()
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
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди или файл не найден"},
    },
)
async def delete_queue_media(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=100)],
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_not_reconciling(item.status)

    safe_name = FilePath(media_id).name
    if safe_name != media_id:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")
    path = media_directory(queue_item_id) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    await asyncio.to_thread(path.unlink)
    return queue_item_response(item)


@router.patch(
    "/{queue_item_id}",
    response_model=QueueItemRead,
    summary="Изменить текст элемента очереди",
    description=(
        "Редактирует подготовленный текст. Статус через PATCH не меняется: "
        "для модерации используются отдельные операции."
    ),
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
    },
)
async def update_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    data: QueueItemUpdate,
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_not_reconciling(item.status)
    changed_fields = sorted(data.model_fields_set)
    item = await repository.update(item, data, commit=False)
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.edited",
        details={"changed_fields": changed_fields},
    )
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/submit",
    response_model=QueueItemRead,
    summary="Отправить пост на модерацию",
    description="Переводит подготовленный пост в статус awaiting_moderation.",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Недопустимый переход статуса"},
    },
)
async def submit_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    session: Session,
    auth: QueueSubmitDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_status(
        item.status,
        {QueueItemStatus.PENDING, QueueItemStatus.REWRITING, QueueItemStatus.REJECTED},
    )
    if not item.rewritten_text or not item.rewritten_text.strip():
        raise conflict_error("Перед отправкой на модерацию нужен подготовленный текст")
    previous_status = item.status.value
    item = await repository.set_status(
        item, QueueItemStatus.AWAITING_MODERATION, commit=False
    )
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.submitted",
        details={"previous_status": previous_status, "status": item.status.value},
    )
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/approve",
    response_model=QueueItemRead,
    summary="Одобрить пост",
    description="Одобряет пост, находящийся на модерации.",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Недопустимый переход статуса"},
    },
)
async def approve_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    session: Session,
    auth: QueueModerateDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_status(item.status, {QueueItemStatus.AWAITING_MODERATION})
    previous_status = item.status.value
    item = await repository.set_status(item, QueueItemStatus.APPROVED, commit=False)
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.approved",
        details={"previous_status": previous_status, "status": item.status.value},
    )
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/reject",
    response_model=QueueItemRead,
    summary="Отклонить пост",
    description="Отклоняет пост, находящийся на модерации.",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Недопустимый переход статуса"},
    },
)
async def reject_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    session: Session,
    auth: QueueModerateDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_status(item.status, {QueueItemStatus.AWAITING_MODERATION})
    previous_status = item.status.value
    item = await repository.set_status(item, QueueItemStatus.REJECTED, commit=False)
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.rejected",
        details={"previous_status": previous_status, "status": item.status.value},
    )
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/reopen",
    response_model=QueueItemRead,
    summary="Вернуть пост в работу",
    description=(
        "Возвращает пост в статус pending для повторного редактирования. "
        "Можно использовать после модерации, одобрения или планирования."
    ),
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Недопустимый переход статуса"},
    },
)
async def reopen_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    session: Session,
    auth: QueueModerateDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
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
    previous_status = item.status.value
    item = await repository.set_status(item, QueueItemStatus.PENDING, commit=False)
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.reopened",
        details={"previous_status": previous_status, "status": item.status.value},
    )
    return queue_item_response(item)


@router.post(
    "/{queue_item_id}/schedule",
    response_model=QueueItemRead,
    summary="Запланировать публикацию",
    description="Назначает время публикации для одобренного поста.",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
        409: {"description": "Недопустимый переход статуса"},
    },
)
async def schedule_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    data: QueueItemSchedule,
    session: Session,
    auth: QueueScheduleDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> QueueItemRead:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_status(item.status, {QueueItemStatus.APPROVED})
    previous_status = item.status.value
    item = await repository.set_status(
        item,
        QueueItemStatus.SCHEDULED,
        scheduled_at=data.scheduled_at,
        commit=False,
    )
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.scheduled",
        details={
            "previous_status": previous_status,
            "status": item.status.value,
            "scheduled_at": data.scheduled_at.isoformat(),
        },
    )
    return queue_item_response(item)


@router.delete(
    "/{queue_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить элемент очереди",
    description="Удаляет редакционный элемент очереди до технической публикации.",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Элемент очереди не найден"},
    },
)
async def delete_queue_item(
    queue_item_id: Annotated[
        int, Path(gt=0, description="Идентификатор элемента очереди")
    ],
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> Response:
    repository = QueueItemRepository(session)
    item = await get_accessible_queue_item(repository, queue_item_id, auth)
    if item is None:
        raise not_found_error()
    ensure_not_reconciling(item.status)
    await record_editorial_event(
        session,
        actor_user_id=auth.user.user_id,
        item=item,
        action="editorial.deleted",
        details={"status": item.status.value},
        commit=False,
    )
    await repository.delete(item)
    await asyncio.to_thread(cleanup_queue_item_media, queue_item_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
