from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import AuditEvent, QueueItem


async def record_editorial_event(
    session: AsyncSession,
    *,
    actor_user_id: int,
    item: QueueItem,
    action: str,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    target = getattr(item, "target", None)
    event_details: dict[str, Any] = {
        "queue_item_id": item.queue_item_id,
        "post_id": item.post_id,
        "target_id": item.target_id,
        "target_name": getattr(target, "name", None),
    }
    if details:
        event_details.update(details)
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            subject_type="queue_item",
            subject_id=item.queue_item_id,
            details=event_details,
        )
    )
    if commit:
        await session.commit()
    else:
        await session.flush()
