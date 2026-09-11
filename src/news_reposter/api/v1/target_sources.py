from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.db.session import get_db_session
from news_reposter.repositories import (
    TargetSourceAlreadyExistsError,
    TargetSourceRepository,
)
from news_reposter.schemas import (
    TargetSourceCreate,
    TargetSourceRead,
    TargetSourceUpdate,
)

router = APIRouter(
    prefix="/targets/{target_id}/sources",
    tags=["Источники целевого канала"],
    responses=API_KEY_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]


def target_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Цель публикации не найдена",
    )


def source_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Источник не найден",
    )


def target_source_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Источник не подключён к этой цели публикации",
    )


def duplicate_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Источник уже подключён к этой цели публикации",
    )


@router.post(
    "",
    response_model=TargetSourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Подключить источник к целевому каналу",
    description=(
        "Связывает существующий источник с конкретной целью публикации и задаёт "
        "настройки использования этого источника в канале."
    ),
    response_description="Подключённый источник",
    responses={
        404: {"description": "Цель публикации или источник не найдены"},
        409: {"description": "Источник уже подключён к этой цели публикации"},
        422: {"description": "Переданы некорректные данные"},
    },
)
async def create_target_source(
    target_id: Annotated[int, Path(gt=0, description="Идентификатор целевого канала")],
    data: TargetSourceCreate,
    session: Session,
    _api_key: ApiKeyDep,
) -> TargetSourceRead:
    repository = TargetSourceRepository(session)
    if not await repository.target_exists(target_id):
        raise target_not_found_error()
    if not await repository.source_exists(data.source_id):
        raise source_not_found_error()
    try:
        item = await repository.create(target_id, data)
    except TargetSourceAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return TargetSourceRead.model_validate(item)


@router.get(
    "",
    response_model=list[TargetSourceRead],
    summary="Получить источники целевого канала",
    description=(
        "Возвращает источники, подключённые к конкретной цели публикации, "
        "с возможностью фильтрации по активности."
    ),
    response_description="Список подключённых источников",
    responses={404: {"description": "Цель публикации не найдена"}},
)
async def list_target_sources(
    target_id: Annotated[int, Path(gt=0, description="Идентификатор целевого канала")],
    session: Session,
    _api_key: ApiKeyDep,
    offset: Annotated[int, Query(ge=0, description="Сколько записей пропустить")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Максимум записей")] = 50,
    is_active: Annotated[
        bool | None,
        Query(description="Фильтр по активным или отключённым источникам"),
    ] = None,
) -> list[TargetSourceRead]:
    repository = TargetSourceRepository(session)
    if not await repository.target_exists(target_id):
        raise target_not_found_error()
    items = await repository.list(
        target_id=target_id,
        offset=offset,
        limit=limit,
        is_active=is_active,
    )
    return [TargetSourceRead.model_validate(item) for item in items]


@router.patch(
    "/{target_source_id}",
    response_model=TargetSourceRead,
    summary="Изменить настройки источника целевого канала",
    description=(
        "Позволяет включить или отключить источник для этого канала и отдельно "
        "управлять рерайтом его постов."
    ),
    response_description="Изменённые настройки источника",
    responses={
        404: {"description": "Связь цели и источника не найдена"},
        422: {"description": "Нет изменений или переданы некорректные данные"},
    },
)
async def update_target_source(
    target_id: Annotated[int, Path(gt=0, description="Идентификатор целевого канала")],
    target_source_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор связи цели и источника"),
    ],
    data: TargetSourceUpdate,
    session: Session,
    _api_key: ApiKeyDep,
) -> TargetSourceRead:
    repository = TargetSourceRepository(session)
    item = await repository.get(target_id, target_source_id)
    if item is None:
        raise target_source_not_found_error()
    item = await repository.update(item, data)
    return TargetSourceRead.model_validate(item)


@router.delete(
    "/{target_source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отключить источник от целевого канала",
    description="Удаляет связь источника с конкретной целью публикации.",
    response_description="Источник отключён от целевого канала",
    responses={404: {"description": "Связь цели и источника не найдена"}},
)
async def delete_target_source(
    target_id: Annotated[int, Path(gt=0, description="Идентификатор целевого канала")],
    target_source_id: Annotated[
        int,
        Path(gt=0, description="Идентификатор связи цели и источника"),
    ],
    session: Session,
    _api_key: ApiKeyDep,
) -> Response:
    repository = TargetSourceRepository(session)
    item = await repository.get(target_id, target_source_id)
    if item is None:
        raise target_source_not_found_error()
    await repository.delete(item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
