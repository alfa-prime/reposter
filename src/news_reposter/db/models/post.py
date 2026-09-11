from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import PostStatus, enum_values
from news_reposter.db.models.types import JSON_DATA

if TYPE_CHECKING:
    from news_reposter.db.models.attachment import PostAttachment
    from news_reposter.db.models.queue_item import QueueItem
    from news_reposter.db.models.source import Source


class Post(Base):
    """Пост, полученный из одного внешнего источника."""

    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_post_id",
            name="uq_posts_source_id_external_post_id",
        ),
        Index("ix_posts_source_id_status", "source_id", "status"),
        Index("ix_posts_status_received_at", "status", "received_at"),
    )

    post_id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.source_id", ondelete="CASCADE"),
        nullable=False,
    )
    external_post_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    original_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            name="post_status",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        default=PostStatus.RECEIVED,
        server_default=PostStatus.RECEIVED.value,
    )
    source_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    received_at: Mapped[datetime] = mapped_column(
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
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)

    source: Mapped["Source"] = relationship(back_populates="posts")
    attachments: Mapped[list["PostAttachment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PostAttachment.position",
    )
    queue_items: Mapped[list["QueueItem"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
