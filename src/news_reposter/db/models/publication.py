from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
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
from news_reposter.db.models.enums import PublicationStatus, enum_values

if TYPE_CHECKING:
    from news_reposter.db.models.post import Post
    from news_reposter.db.models.target import Target


class Publication(Base):
    """Попытка публикации одного поста в одной цели."""

    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "target_id",
            name="uq_publications_post_id_target_id",
        ),
        CheckConstraint("attempts >= 0", name="ck_publications_attempts"),
        Index("ix_publications_status_created_at", "status", "created_at"),
    )

    publication_id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.target_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[PublicationStatus] = mapped_column(
        Enum(
            PublicationStatus,
            name="publication_status",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        default=PublicationStatus.PENDING,
        server_default=PublicationStatus.PENDING.value,
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    publication_url: Mapped[str | None] = mapped_column(String(2048))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

    post: Mapped["Post"] = relationship(back_populates="publications")
    target: Mapped["Target"] = relationship(back_populates="publications")
