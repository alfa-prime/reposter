from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.enums import PublicationAttemptStatus, enum_values

if TYPE_CHECKING:
    from news_reposter.db.models.publication import Publication
    from news_reposter.db.models.user import User


class PublicationAttempt(Base):
    """Одна техническая попытка отправить материал во внешнюю платформу."""

    __tablename__ = "publication_attempts"
    __table_args__ = (
        Index(
            "ix_publication_attempts_publication_started",
            "publication_id",
            "started_at",
        ),
        Index("ix_publication_attempts_status_started", "status", "started_at"),
    )

    publication_attempt_id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("publications.publication_id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PublicationAttemptStatus] = mapped_column(
        Enum(
            PublicationAttemptStatus,
            name="publication_attempt_status",
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
        ),
        nullable=False,
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    initiated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    prepared_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    check_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    publication_url: Mapped[str | None] = mapped_column(String(2048))
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    publication: Mapped["Publication"] = relationship(back_populates="attempt_history")
    initiated_by: Mapped["User | None"] = relationship()
