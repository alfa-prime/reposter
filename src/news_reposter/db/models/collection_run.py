from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import (
    CollectionRunStatus,
    CollectionRunTrigger,
    enum_values,
)

if TYPE_CHECKING:
    from news_reposter.db.models.collection_source_run import CollectionSourceRun


class CollectionRun(Base):
    """Один ручной или плановый проход по активным источникам."""

    __tablename__ = "collection_runs"

    collection_run_id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[CollectionRunTrigger] = mapped_column(
        Enum(
            CollectionRunTrigger,
            name="collection_run_trigger",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[CollectionRunStatus] = mapped_column(
        Enum(
            CollectionRunStatus,
            name="collection_run_status",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        nullable=False,
        default=CollectionRunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sources_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posts_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queue_items_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    source_runs: Mapped[list["CollectionSourceRun"]] = relationship(
        back_populates="collection_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CollectionSourceRun.collection_source_run_id",
    )
