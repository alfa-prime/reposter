import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    HttpClientDep,
    SameOriginDep,
    require_permission,
)
from news_reposter.api.v1.max import (
    max_bad_gateway,
    max_client_from_settings,
    normalize_max_link,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.db.models import MAXChannel
from news_reposter.db.session import get_db_session
from news_reposter.integrations.max import MAXAPIError
from news_reposter.repositories import TargetAlreadyExistsError, TargetRepository
from news_reposter.schemas import TargetCreate, TargetRead, TargetUpdate
from news_reposter.services.media_storage import cleanup_queue_items_media

router = APIRouter(
    prefix="/targets",
    tags=["Цели публикаций"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
TargetsReadDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.TARGETS_READ)),
]
TargetsManageDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.TARGETS_MANAGE)),
]


def not_found_error() -> HTTPException:
    """Формирует единый ответ для отсутствующей цели публикации."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Цель публикации не найдена",
    )


def duplicate_error() -> HTTPException:
    """Формирует ответ при повторном добавлении цели публикации."""

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Такая цель публикации уже существует",
    )


def _max_icon_url(chat: dict[str, Any]) -> str | None:
    """Извлекает URL аватара из разных вариантов объекта icon MAX."""

    icon = chat.get("icon")
    if isinstance(icon, str) and icon.startswith(("http://", "https://")):
        return icon
    if not isinstance(icon, dict):
        return None

    preferred = ("url", "large", "small", "photo_200", "photo_100")
    for key in preferred:
        value = icon.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value

    for value in icon.values():
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
        if isinstance(value, dict):
            nested = _max_icon_url({"icon": value})
            if nested:
                return nested
    return None


@router.post(
    "",
    response_model=TargetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить цель публикации",
    description=(
        "Создаёт канал или чат, в который приложение сможет отправлять посты. "
        "Пара `platform + external_id` должна быть уникальной."
    ),
    response_description="Созданная цель публикации",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        409: {"description": "Такая цель публикации уже существует"},
        422: {"description": "Переданы некорректные данные"},
    },
)
async def create_target(
    data: TargetCreate,
    session: Session,
    _auth: TargetsManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> TargetRead:
    """Добавляет новую цель публикации."""

    repository = TargetRepository(session)
    try:
        target = await repository.create(data)
    except TargetAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return TargetRead.model_validate(target)


@router.get(
    "",
    response_model=list[TargetRead],
    summary="Получить список целей",
    description=(
        "Возвращает цели по возрастанию `target_id`. Результат можно "
        "отфильтровать по платформе и активности."
    ),
    response_description="Список найденных целей публикаций",
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_targets(
    session: Session,
    auth: TargetsReadDep,
    offset: Annotated[
        int,
        Query(ge=0, description="Сколько записей пропустить от начала списка"),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Максимальное количество записей"),
    ] = 50,
    platform: Annotated[
        str | None,
        Query(
            min_length=2,
            max_length=32,
            description="Оставить только цели указанной платформы",
            examples=["max"],
        ),
    ] = None,
    is_active: Annotated[
        bool | None,
        Query(description="Фильтр по включённым или приостановленным целям"),
    ] = None,
) -> list[TargetRead]:
    """Возвращает список целей публикаций с необязательными фильтрами."""

    target_ids = getattr(auth, "target_ids", None)
    access_filter = {} if target_ids is None else {"allowed_target_ids": target_ids}
    targets = await TargetRepository(session).list(
        offset=offset,
        limit=limit,
        platform=platform.lower() if platform else None,
        is_active=is_active,
        **access_filter,
    )
    return [TargetRead.model_validate(target) for target in targets]


@router.get(
    "/resolve-max",
    summary="Определить канал MAX по ссылке",
    description="Возвращает chat_id, название и аватар канала MAX по публичной ссылке.",
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Канал ещё не обнаружен webhook-ом"},
    },
)
async def resolve_max_target(
    _auth: TargetsManageDep,
    session: Session,
    http_client: HttpClientDep,
    link: str = Query(description="Публичная ссылка MAX"),
) -> dict[str, Any]:
    try:
        normalized = normalize_max_link(link)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    channel = await session.scalar(
        select(MAXChannel).where(
            MAXChannel.link == normalized,
            MAXChannel.is_active.is_(True),
        )
    )
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Канал ещё не обнаружен. Добавьте бота в подписчики канала и назначьте "
                "администратором. Если бот уже был добавлен раньше, удалите его и добавьте снова."
            ),
        )

    try:
        chat = await max_client_from_settings(http_client).get_chat(channel.chat_id)
    except MAXAPIError as exc:
        raise max_bad_gateway(exc) from exc

    title = chat.get("title")
    return {
        "chat_id": channel.chat_id,
        "title": title if isinstance(title, str) and title.strip() else channel.title,
        "link": normalized,
        "icon_url": _max_icon_url(chat),
    }


@router.get(
    "/{target_id}",
    response_model=TargetRead,
    summary="Получить цель публикации",
    description="Возвращает один канал или чат по его ID в нашей базе.",
    response_description="Найденная цель публикации",
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Цель публикации не найдена"},
    },
)
async def get_target(
    target_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор цели в нашей базе"),
    ],
    session: Session,
    auth: TargetsReadDep,
) -> TargetRead:
    """Возвращает одну цель публикации по идентификатору."""

    target = await TargetRepository(session).get(target_id)
    target_ids = getattr(auth, "target_ids", None)
    if target is None or (target_ids is not None and target_id not in target_ids):
        raise not_found_error()
    return TargetRead.model_validate(target)


@router.patch(
    "/{target_id}",
    response_model=TargetRead,
    summary="Изменить цель публикации",
    description=(
        "Частично изменяет цель. Для временной остановки публикаций достаточно "
        "установить `is_active` в `false`; значение `url=null` удаляет ссылку."
    ),
    response_description="Изменённая цель публикации",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Цель публикации не найдена"},
        409: {"description": "Такая цель публикации уже существует"},
        422: {"description": "Нет изменений или переданы некорректные данные"},
    },
)
async def update_target(
    target_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор цели в нашей базе"),
    ],
    data: TargetUpdate,
    session: Session,
    _auth: TargetsManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> TargetRead:
    """Частично изменяет цель публикации."""

    repository = TargetRepository(session)
    target = await repository.get(target_id)
    if target is None:
        raise not_found_error()
    try:
        target = await repository.update(target, data)
    except TargetAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return TargetRead.model_validate(target)


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить цель публикации",
    description=(
        "Удаляет цель. Если с ней уже связаны публикации, вместо удаления следует "
        "приостановить её через `is_active=false`."
    ),
    response_description="Цель публикации удалена",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        404: {"description": "Цель публикации не найдена"},
    },
)
async def delete_target(
    target_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор цели в нашей базе"),
    ],
    session: Session,
    _auth: TargetsManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> Response:
    """Удаляет цель публикации."""

    repository = TargetRepository(session)
    target = await repository.get(target_id)
    if target is None:
        raise not_found_error()
    queue_item_ids = await repository.queue_item_ids(target_id)
    await repository.delete(target)
    await asyncio.to_thread(cleanup_queue_items_media, queue_item_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
