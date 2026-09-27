from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class TaskOutbox(Base):
    __tablename__ = "task_outbox"
    __table_args__ = (Index("ix_task_outbox_dispatch", "delivered_at", "available_at"),)
    outbox_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("background_tasks.task_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    queue: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))


class TaskDelivery(Base):
    """Durable receipt used by the pre-Celery PostgreSQL transport."""

    __tablename__ = "task_deliveries"
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("background_tasks.task_id", ondelete="CASCADE"), primary_key=True
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
