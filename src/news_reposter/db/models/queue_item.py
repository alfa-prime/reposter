from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import QueueItemStatus, enum_values

if TYPE_CHECKING:
    from news_reposter.db.models.post import Post
    from news_reposter.db.models.publication import Publication
    from news_reposter.db.models.target import Target


class QueueItem(Base):
    """Редакционная версия исходного поста для конкретной цели публикации."""

    __tablename__ = "queue_items"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "target_id",
            name="uq_queue_items_post_id_target_id",
        ),
        Index("ix_queue_items_target_id_status", "target_id", "status"),
        Index("ix_queue_items_status_scheduled_at", "status", "scheduled_at"),
    )

    queue_item_id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.target_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rewritten_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[QueueItemStatus] = mapped_column(
        Enum(
            QueueItemStatus,
            name="queue_item_status",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        default=QueueItemStatus.PENDING,
        server_default=QueueItemStatus.PENDING.value,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    post: Mapped["Post"] = relationship(back_populates="queue_items")
    target: Mapped["Target"] = relationship(back_populates="queue_items")
    publication: Mapped["Publication | None"] = relationship(
        back_populates="queue_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
