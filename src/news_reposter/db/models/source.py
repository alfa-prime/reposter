from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base

if TYPE_CHECKING:
    from news_reposter.db.models.post import Post


class Source(Base):
    """Источник, из которого приложение получает публикации."""

    __tablename__ = "sources"
    __table_args__ = (
        Index("ix_sources_platform_is_active", "platform", "is_active"),
    )

    source_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(String(2048), unique=True)
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

    posts: Mapped[list["Post"]] = relationship(
        back_populates="source",
        passive_deletes=True,
    )
