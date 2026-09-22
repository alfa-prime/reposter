from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    SameOriginDep,
    require_permission,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.db.models import CollectionRunStatus, CollectionRunTrigger
from news_reposter.db.session import get_db_session
from news_reposter.repositories.collection import CollectionRepository
from news_reposter.schemas.collection import (
    CollectionRunDetail,
    CollectionRunPage,
    CollectionRunRead,
    CollectionSettingsRead,
    CollectionSettingsUpdate,
    CollectionStatusRead,
)
from news_reposter.services.scheduler import CollectionSchedule, next_run_at

router = APIRouter(
    prefix="/system/collection",
    tags=["Планировщик сбора"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
SchedulerReadDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.SCHEDULER_READ)),
]
SchedulerManageDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.SCHEDULER_MANAGE)),
]


@router.get(
    "/settings",
    response_model=CollectionSettingsRead,
    responses=PERMISSION_AUTH_RESPONSES,
)
async def get_collection_settings(
    session: Session,
    _auth: SchedulerReadDep,
) -> CollectionSettingsRead:
    settings = await CollectionRepository(session).get_settings()
    return CollectionSettingsRead.model_validate(settings)


@router.put(
    "/settings",
    response_model=CollectionSettingsRead,
    responses=PERMISSION_CSRF_AUTH_RESPONSES,
)
async def update_collection_settings(
    data: CollectionSettingsUpdate,
    request: Request,
    session: Session,
    _auth: SchedulerManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> CollectionSettingsRead:
    repository = CollectionRepository(session)
    settings = await repository.get_settings()
    settings = await repository.update_settings(settings, **data.model_dump())
    scheduler = getattr(request.app.state, "collection_scheduler", None)
    if scheduler is not None:
        scheduler.notify_settings_changed()
    return CollectionSettingsRead.model_validate(settings)


@router.get(
    "/status",
    response_model=CollectionStatusRead,
    responses=PERMISSION_AUTH_RESPONSES,
)
async def get_collection_status(
    session: Session,
    _auth: SchedulerReadDep,
) -> CollectionStatusRead:
    repository = CollectionRepository(session)
    settings = await repository.get_settings()
    latest = await repository.latest_run()
    latest_success = await repository.latest_success()
    schedule = CollectionSchedule.from_model(settings)
    next_run = (
        next_run_at(datetime.now(schedule.zoneinfo()), schedule)
        if schedule.enabled
        else None
    )
    return CollectionStatusRead(
        enabled=settings.enabled,
        running=latest is not None and latest.status == CollectionRunStatus.RUNNING,
        next_run_at=next_run,
        last_run=(CollectionRunRead.model_validate(latest) if latest else None),
        last_success_at=(latest_success.finished_at if latest_success else None),
        consecutive_failures=await repository.consecutive_failures(),
    )


@router.get(
    "/runs",
    response_model=CollectionRunPage,
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_collection_runs(
    session: Session,
    _auth: SchedulerReadDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    run_status: Annotated[CollectionRunStatus | None, Query(alias="status")] = None,
    trigger: CollectionRunTrigger | None = None,
) -> CollectionRunPage:
    items, total = await CollectionRepository(session).list_runs(
        offset=offset,
        limit=limit,
        status=run_status,
        trigger=trigger,
    )
    return CollectionRunPage(
        items=[CollectionRunRead.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/runs/{run_id}",
    response_model=CollectionRunDetail,
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Запуск не найден"},
    },
)
async def get_collection_run(
    run_id: Annotated[int, Path(gt=0)],
    session: Session,
    _auth: SchedulerReadDep,
) -> CollectionRunDetail:
    run = await CollectionRepository(session).get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запуск сборщика не найден",
        )
    return CollectionRunDetail.model_validate(run)
