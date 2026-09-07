from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class Target(Base):
    """Канал или чат, в который приложение публикует записи."""

    __tablename__ = "targets"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_id",
            name="uq_targets_platform_external_id",
        ),
        Index("ix_targets_platform_is_active", "platform", "is_active"),
    )

    target_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(
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
