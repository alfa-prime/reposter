from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class AuditEvent(Base):
    """Неизменяемая запись о значимом административном действии."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_created_at", "created_at"),
        Index(
            "ix_audit_events_subject_page",
            "subject_type",
            "created_at",
            "audit_event_id",
        ),
        Index(
            "ix_audit_events_actor_page",
            "subject_type",
            "actor_user_id",
            "created_at",
            "audit_event_id",
        ),
        Index(
            "ix_audit_events_action_page",
            "subject_type",
            "action",
            "created_at",
            "audit_event_id",
        ),
        Index(
            "ix_audit_events_material_page",
            "subject_type",
            "subject_id",
            "created_at",
            "audit_event_id",
        ),
        Index(
            "ix_audit_events_target_page",
            "subject_type",
            "target_id",
            "created_at",
            "audit_event_id",
        ),
    )

    audit_event_id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Historical channel snapshot: deliberately no FK, survives channel deletion.
    target_id: Mapped[int | None] = mapped_column(
        Integer,
        Computed(
            "CASE WHEN subject_type = 'queue_item' AND details->>'target_id' ~ '^[0-9]{1,10}$' THEN CASE WHEN (details->>'target_id')::bigint BETWEEN 1 AND 2147483647 THEN (details->>'target_id')::integer END END",
            persisted=True,
        ),
        nullable=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
