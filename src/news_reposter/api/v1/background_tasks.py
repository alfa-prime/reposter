from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    AuthContextDep,
    CsrfAuthContextDep,
    SameOriginDep,
)
from news_reposter.auth.rbac import PermissionCode
from news_reposter.background.contracts import TaskQueue, TaskState
from news_reposter.db.models import BackgroundTask
from news_reposter.db.session import get_db_session
from news_reposter.schemas.background_task import TaskRead

router = APIRouter(
    prefix="/tasks", tags=["Система"], responses=PERMISSION_AUTH_RESPONSES
)
Session = Annotated[AsyncSession, Depends(get_db_session)]
PERMISSIONS = {
    TaskQueue.REWRITE: PermissionCode.QUEUE_READ,
    TaskQueue.PUBLICATION: PermissionCode.QUEUE_READ,
    TaskQueue.COLLECTION: PermissionCode.SCHEDULER_READ,
}


def check_task_access(task, auth):
    if auth.user.must_change_password:
        raise HTTPException(
            status_code=403, detail="Требуется сменить временный пароль"
        )
    if "administrator" in auth.role_codes:
        return
    if (
        task.queue == TaskQueue.MAINTENANCE
        or PERMISSIONS[task.queue].value not in auth.permission_codes
    ):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if task.target_id is not None and not auth.can_access_target(task.target_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if task.actor_user_id not in {None, auth.user.user_id}:
        raise HTTPException(status_code=404, detail="Задача не найдена")


@router.get(
    "/{task_id}", response_model=TaskRead, summary="Получить состояние фоновой задачи"
)
async def get_task(task_id: UUID, auth: AuthContextDep, session: Session):
    task = await session.get(BackgroundTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    check_task_access(task, auth)
    return TaskRead.model_validate(task)


@router.post(
    "/{task_id}/cancel",
    response_model=TaskRead,
    responses=PERMISSION_CSRF_AUTH_RESPONSES,
    summary="Отменить ожидающую фоновую задачу",
)
async def cancel_task(
    task_id: UUID,
    auth: AuthContextDep,
    session: Session,
    _csrf: CsrfAuthContextDep,
    _origin: SameOriginDep,
):
    task = await session.scalar(
        select(BackgroundTask)
        .where(BackgroundTask.task_id == task_id)
        .with_for_update()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    check_task_access(task, auth)
    if (
        "administrator" not in auth.role_codes
        and task.actor_user_id != auth.user.user_id
    ):
        raise HTTPException(status_code=403, detail="Нельзя отменить системную задачу")
    if task.state == TaskState.CANCELLED:
        return TaskRead.model_validate(task)
    if task.state not in {TaskState.PENDING, TaskState.RETRY_WAIT}:
        raise HTTPException(
            status_code=409, detail="Задача уже выполняется или завершена"
        )
    task.state = TaskState.CANCELLED
    task.finished_at = await session.scalar(select(func.now()))
    await session.commit()
    return TaskRead.model_validate(task)
