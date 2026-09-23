from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class UserTarget(Base):
    """Назначение канала публикации пользователю."""

    __tablename__ = "user_targets"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "target_id", name="pk_user_targets"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.target_id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
