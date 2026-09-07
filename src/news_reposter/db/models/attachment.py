from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import AttachmentType, enum_values
from news_reposter.db.models.types import JSON_DATA

if TYPE_CHECKING:
    from news_reposter.db.models.post import Post


class PostAttachment(Base):
    """Фотография, видео или другое вложение исходного поста."""

    __tablename__ = "post_attachments"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "position",
            name="uq_post_attachments_post_id_position",
        ),
        CheckConstraint("position >= 0", name="ck_post_attachments_position"),
    )

    attachment_id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attachment_type: Mapped[AttachmentType] = mapped_column(
        Enum(
            AttachmentType,
            name="attachment_type",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        )
    )
    external_attachment_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    post: Mapped["Post"] = relationship(back_populates="attachments")
