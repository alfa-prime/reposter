from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.session import get_db_session
from news_reposter.repositories import SourceAlreadyExistsError, SourceRepository
from news_reposter.schemas import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["Sources"])
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


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(data: SourceCreate, session: Session) -> SourceRead:
    """Добавляет новый источник публикаций."""

    repository = SourceRepository(session)
    try:
        source = await repository.create(data)
    except SourceAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return SourceRead.model_validate(source)


@router.get("", response_model=list[SourceRead])
async def list_sources(
    session: Session,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    platform: Annotated[str | None, Query(min_length=2, max_length=32)] = None,
    is_active: bool | None = None,
) -> list[SourceRead]:
    """Возвращает список источников с необязательными фильтрами."""

    sources = await SourceRepository(session).list(
        offset=offset,
        limit=limit,
        platform=platform.lower() if platform else None,
        is_active=is_active,
    )
    return [SourceRead.model_validate(source) for source in sources]


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(source_id: int, session: Session) -> SourceRead:
    """Возвращает один источник по идентификатору."""

    source = await SourceRepository(session).get(source_id)
    if source is None:
        raise not_found_error()
    return SourceRead.model_validate(source)


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int,
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


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: int, session: Session) -> Response:
    """Удаляет источник."""

    repository = SourceRepository(session)
    source = await repository.get(source_id)
    if source is None:
        raise not_found_error()
    await repository.delete(source)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
