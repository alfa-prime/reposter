from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base

if TYPE_CHECKING:
    from news_reposter.db.models.source import Source
    from news_reposter.db.models.target import Target


class TargetSource(Base):
    """Настройки использования одного источника в одной цели публикации."""

    __tablename__ = "target_sources"
    __table_args__ = (
        UniqueConstraint(
            "target_id",
            "source_id",
            name="uq_target_sources_target_id_source_id",
        ),
        Index("ix_target_sources_target_id_is_active", "target_id", "is_active"),
    )

    target_source_id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.target_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.source_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    rewrite_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
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

    target: Mapped["Target"] = relationship(back_populates="target_sources")
    source: Mapped["Source"] = relationship(back_populates="target_sources")
