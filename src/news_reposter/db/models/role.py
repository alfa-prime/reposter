from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, false, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base

if TYPE_CHECKING:
    from news_reposter.db.models.permission import Permission
    from news_reposter.db.models.user import User


class Role(Base):
    """Редактируемый набор разрешений, назначаемый пользователям."""

    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
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

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions",
        back_populates="roles",
        passive_deletes=True,
    )
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles",
        back_populates="roles",
        passive_deletes=True,
    )
