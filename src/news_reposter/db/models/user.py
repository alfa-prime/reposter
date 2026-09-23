from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base

if TYPE_CHECKING:
    from news_reposter.db.models.login_attempt import LoginAttempt
    from news_reposter.db.models.role import Role
    from news_reposter.db.models.target import Target
    from news_reposter.db.models.user_session import UserSession


class User(Base):
    """Пользователь редакционной системы."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "length(username_normalized) BETWEEN 3 AND 64",
            name="username_normalized_length",
        ),
        CheckConstraint(
            "length(display_name) BETWEEN 1 AND 200",
            name="display_name_length",
        ),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    username_normalized: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles",
        back_populates="users",
        passive_deletes=True,
    )
    targets: Mapped[list["Target"]] = relationship(
        secondary="user_targets",
        back_populates="users",
        passive_deletes=True,
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
    login_attempts: Mapped[list["LoginAttempt"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
