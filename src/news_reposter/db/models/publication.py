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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import PublicationStatus, enum_values

if TYPE_CHECKING:
    from news_reposter.db.models.queue_item import QueueItem


class Publication(Base):
    """Техническое состояние публикации одного элемента редакционной очереди."""

    __tablename__ = "publications"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_publications_attempts"),
        Index("ix_publications_status_created_at", "status", "created_at"),
    )

    publication_id: Mapped[int] = mapped_column(primary_key=True)
    queue_item_id: Mapped[int] = mapped_column(
        ForeignKey("queue_items.queue_item_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
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

    queue_item: Mapped["QueueItem"] = relationship(back_populates="publication")
