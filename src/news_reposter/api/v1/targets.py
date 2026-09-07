from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.session import get_db_session
from news_reposter.repositories import TargetAlreadyExistsError, TargetRepository
from news_reposter.schemas import TargetCreate, TargetRead, TargetUpdate

router = APIRouter(prefix="/targets", tags=["Targets"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


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


@router.post("", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
async def create_target(data: TargetCreate, session: Session) -> TargetRead:
    """Добавляет новую цель публикации."""

    repository = TargetRepository(session)
    try:
        target = await repository.create(data)
    except TargetAlreadyExistsError as exc:
        raise duplicate_error() from exc
    return TargetRead.model_validate(target)


@router.get("", response_model=list[TargetRead])
async def list_targets(
    session: Session,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    platform: Annotated[str | None, Query(min_length=2, max_length=32)] = None,
    is_active: bool | None = None,
) -> list[TargetRead]:
    """Возвращает список целей публикаций с необязательными фильтрами."""

    targets = await TargetRepository(session).list(
        offset=offset,
        limit=limit,
        platform=platform.lower() if platform else None,
        is_active=is_active,
    )
    return [TargetRead.model_validate(target) for target in targets]


@router.get("/{target_id}", response_model=TargetRead)
async def get_target(target_id: int, session: Session) -> TargetRead:
    """Возвращает одну цель публикации по идентификатору."""

    target = await TargetRepository(session).get(target_id)
    if target is None:
        raise not_found_error()
    return TargetRead.model_validate(target)


@router.patch("/{target_id}", response_model=TargetRead)
async def update_target(
    target_id: int,
    data: TargetUpdate,
    session: Session,
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


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(target_id: int, session: Session) -> Response:
    """Удаляет цель публикации."""

    repository = TargetRepository(session)
    target = await repository.get(target_id)
    if target is None:
        raise not_found_error()
    await repository.delete(target)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
