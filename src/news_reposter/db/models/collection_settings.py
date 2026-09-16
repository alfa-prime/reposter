from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class CollectionSettings(Base):
    """Редактируемое расписание автоматического сбора источников."""

    __tablename__ = "collection_settings"
    __table_args__ = (
        CheckConstraint("collection_settings_id = 1", name="singleton"),
        CheckConstraint(
            "interval_minutes >= 1 AND interval_minutes <= 1440",
            name="interval_minutes_range",
        ),
        CheckConstraint("start_time <> end_time", name="different_times"),
    )

    collection_settings_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15,
    )
    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(hour=8),
    )
    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(hour=20),
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Europe/Moscow",
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
