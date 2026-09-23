from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from news_reposter.api.dependencies import PERMISSION_AUTH_RESPONSES, require_permission
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.db.models import AuditEvent, QueueItem, User
from news_reposter.db.session import get_db_session
from news_reposter.schemas.audit import (
    AuditEventPage,
    AuditEventRead,
    EditorialAuditEventPage,
    EditorialAuditEventRead,
)

router = APIRouter(prefix="/admin/audit", tags=["Администрирование"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
AuditReadDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.AUDIT_READ)),
]


@router.get(
    "",
    response_model=AuditEventPage,
    summary="Получить журнал действий пользователей",
    description=(
        "Возвращает административные действия с учётными записями, "
        "исполнителей и краткие сведения об изменениях."
    ),
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_audit_events(
    session: Session,
    _auth: AuditReadDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    actor_user_id: Annotated[int | None, Query(gt=0)] = None,
    action: str | None = None,
) -> AuditEventPage:
    actor = aliased(User)
    subject = aliased(User)
    filters = [AuditEvent.subject_type == "user"]
    if actor_user_id is not None:
        filters.append(AuditEvent.actor_user_id == actor_user_id)
    if action:
        filters.append(AuditEvent.action == action)

    total = await session.scalar(
        select(func.count(AuditEvent.audit_event_id)).where(*filters)
    )
    rows = (
        await session.execute(
            select(AuditEvent, actor, subject)
            .outerjoin(actor, actor.user_id == AuditEvent.actor_user_id)
            .outerjoin(
                subject,
                (AuditEvent.subject_type == "user")
                & (subject.user_id == AuditEvent.subject_id),
            )
            .where(*filters)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.audit_event_id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return AuditEventPage(
        items=[
            AuditEventRead(
                audit_event_id=event.audit_event_id,
                actor_user_id=event.actor_user_id,
                actor_name=actor_user.display_name if actor_user else None,
                actor_username=actor_user.username if actor_user else None,
                action=event.action,
                subject_type=event.subject_type,
                subject_id=event.subject_id,
                subject_name=subject_user.display_name if subject_user else None,
                subject_username=subject_user.username if subject_user else None,
                details=event.details,
                created_at=event.created_at,
            )
            for event, actor_user, subject_user in rows
        ],
        total=total or 0,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/editorial",
    response_model=EditorialAuditEventPage,
    summary="Получить редакционный журнал",
    description="Возвращает историю подготовки, модерации и публикации материалов.",
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_editorial_audit_events(
    session: Session,
    _auth: AuditReadDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    actor_user_id: Annotated[int | None, Query(gt=0)] = None,
    target_id: Annotated[int | None, Query(gt=0)] = None,
    queue_item_id: Annotated[int | None, Query(gt=0)] = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> EditorialAuditEventPage:
    actor = aliased(User)
    filters = [AuditEvent.subject_type == "queue_item"]
    if actor_user_id is not None:
        filters.append(AuditEvent.actor_user_id == actor_user_id)
    if target_id is not None:
        filters.append(AuditEvent.details["target_id"].as_integer() == target_id)
    if queue_item_id is not None:
        filters.append(AuditEvent.subject_id == queue_item_id)
    if action:
        filters.append(AuditEvent.action == action)
    if date_from is not None:
        filters.append(AuditEvent.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditEvent.created_at <= date_to)

    total = await session.scalar(
        select(func.count(AuditEvent.audit_event_id)).where(*filters)
    )
    rows = (
        await session.execute(
            select(AuditEvent, actor, QueueItem.queue_item_id)
            .outerjoin(actor, actor.user_id == AuditEvent.actor_user_id)
            .outerjoin(
                QueueItem,
                (AuditEvent.subject_type == "queue_item")
                & (QueueItem.queue_item_id == AuditEvent.subject_id),
            )
            .where(*filters)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.audit_event_id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return EditorialAuditEventPage(
        items=[
            EditorialAuditEventRead(
                audit_event_id=event.audit_event_id,
                actor_user_id=event.actor_user_id,
                actor_name=actor_user.display_name if actor_user else None,
                actor_username=actor_user.username if actor_user else None,
                action=event.action,
                queue_item_id=event.subject_id,
                post_id=event.details.get("post_id"),
                target_id=event.details.get("target_id"),
                target_name=event.details.get("target_name"),
                material_exists=existing_queue_item_id is not None,
                details=event.details,
                created_at=event.created_at,
            )
            for event, actor_user, existing_queue_item_id in rows
        ],
        total=total or 0,
        offset=offset,
        limit=limit,
    )
