from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class MAXChannel(Base):
    """Канал MAX, обнаруженный через webhook-события бота."""

    __tablename__ = "max_channels"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    link: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    last_event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
