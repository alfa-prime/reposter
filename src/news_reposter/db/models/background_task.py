from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.background.contracts import TaskQueue, TaskState
from news_reposter.db.base import Base
from news_reposter.db.models.enums import enum_values


class BackgroundTask(Base):
    __tablename__ = "background_tasks"
    __table_args__ = (
        Index("ix_background_tasks_ready", "queue", "state", "available_at"),
        Index("ix_background_tasks_lease", "state", "lease_until"),
        Index(
            "uq_background_tasks_active_subject",
            "queue",
            "subject_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending', 'running', 'retry_wait') AND subject_id IS NOT NULL"
            ),
        ),
    )
    task_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    queue: Mapped[TaskQueue] = mapped_column(
        Enum(
            TaskQueue,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            name="background_task_queue",
        ),
        nullable=False,
    )
    state: Mapped[TaskState] = mapped_column(
        Enum(
            TaskState,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            name="background_task_state",
        ),
        nullable=False,
        default=TaskState.PENDING,
        server_default="pending",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Historical identifiers; deletion must not turn a user job into a system job.
    actor_user_id: Mapped[int | None] = mapped_column(Integer)
    subject_id: Mapped[int | None] = mapped_column(Integer)
    target_id: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
