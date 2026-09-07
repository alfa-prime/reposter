from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.session import get_db_session
from news_reposter.repositories import SourceAlreadyExistsError, SourceRepository
from news_reposter.schemas import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["Источники"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


def not_found_error() -> HTTPException:
    """Формирует единый ответ для отсутствующего источника."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Источник не найден",
    )


def duplicate_error() -> HTTPException:
    """Формирует ответ при повторном добавлении ссылки."""

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Источник с такой ссылкой уже существует",
    )


@router.post(
    "",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить источник",
    description=(
        "Создаёт источник, из которого позже будут автоматически получаться "
        "публикации. Ссылка должна быть уникальной."
    ),
    response_description="Созданный источник",
    responses={
        409: {"description": "Источник с такой ссылкой уже существует"},
        422: {"description": "Переданы некорректные данные"},
    },
)
async def create_source(data: SourceCreate, session: Session) -> SourceRead:
    """Добавляет новый источник публикаций."""

    repository = SourceRepository(session)
    try:
        source = await repository.create(data)
    except SourceAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return SourceRead.model_validate(source)


@router.get(
    "",
    response_model=list[SourceRead],
    summary="Получить список источников",
    description=(
        "Возвращает источники по возрастанию `source_id`. Результат можно "
        "отфильтровать по платформе и активности."
    ),
    response_description="Список найденных источников",
)
async def list_sources(
    session: Session,
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
            description="Оставить только источники указанной платформы",
            examples=["vk"],
        ),
    ] = None,
    is_active: Annotated[
        bool | None,
        Query(description="Фильтр по включённым или приостановленным источникам"),
    ] = None,
) -> list[SourceRead]:
    """Возвращает список источников с необязательными фильтрами."""

    sources = await SourceRepository(session).list(
        offset=offset,
        limit=limit,
        platform=platform.lower() if platform else None,
        is_active=is_active,
    )
    return [SourceRead.model_validate(source) for source in sources]


@router.get(
    "/{source_id}",
    response_model=SourceRead,
    summary="Получить источник",
    description="Возвращает один источник по его ID в нашей базе.",
    response_description="Найденный источник",
    responses={404: {"description": "Источник не найден"}},
)
async def get_source(
    source_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор источника в нашей базе"),
    ],
    session: Session,
) -> SourceRead:
    """Возвращает один источник по идентификатору."""

    source = await SourceRepository(session).get(source_id)
    if source is None:
        raise not_found_error()
    return SourceRead.model_validate(source)


@router.patch(
    "/{source_id}",
    response_model=SourceRead,
    summary="Изменить источник",
    description=(
        "Частично изменяет источник. Передавать все поля не требуется; для "
        "приостановки достаточно установить `is_active` в `false`."
    ),
    response_description="Изменённый источник",
    responses={
        404: {"description": "Источник не найден"},
        409: {"description": "Источник с такой ссылкой уже существует"},
        422: {"description": "Нет изменений или переданы некорректные данные"},
    },
)
async def update_source(
    source_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор источника в нашей базе"),
    ],
    data: SourceUpdate,
    session: Session,
) -> SourceRead:
    """Частично изменяет источник."""

    repository = SourceRepository(session)
    source = await repository.get(source_id)
    if source is None:
        raise not_found_error()
    try:
        source = await repository.update(source, data)
    except SourceAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return SourceRead.model_validate(source)


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить источник",
    description=(
        "Удаляет источник. Если с ним уже связаны посты, вместо удаления следует "
        "приостановить источник через `is_active=false`."
    ),
    response_description="Источник удалён",
    responses={404: {"description": "Источник не найден"}},
)
async def delete_source(
    source_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор источника в нашей базе"),
    ],
    session: Session,
) -> Response:
    """Удаляет источник."""

    repository = SourceRepository(session)
    source = await repository.get(source_id)
    if source is None:
        raise not_found_error()
    await repository.delete(source)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
