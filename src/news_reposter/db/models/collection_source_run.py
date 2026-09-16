from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import CollectionSourceRunStatus, enum_values

if TYPE_CHECKING:
    from news_reposter.db.models.collection_run import CollectionRun
    from news_reposter.db.models.source import Source


class CollectionSourceRun(Base):
    """Результат обработки одного источника внутри общего прохода."""

    __tablename__ = "collection_source_runs"

    collection_source_run_id: Mapped[int] = mapped_column(primary_key=True)
    collection_run_id: Mapped[int] = mapped_column(
        ForeignKey("collection_runs.collection_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.source_id", ondelete="SET NULL"),
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[CollectionSourceRunStatus] = mapped_column(
        Enum(
            CollectionSourceRunStatus,
            name="collection_source_run_status",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        nullable=False,
        default=CollectionSourceRunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_post_id_before: Mapped[str | None] = mapped_column(String(255))
    last_post_id_after: Mapped[str | None] = mapped_column(String(255))
    posts_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queue_items_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_type: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)

    collection_run: Mapped["CollectionRun"] = relationship(back_populates="source_runs")
    source: Mapped["Source | None"] = relationship()
