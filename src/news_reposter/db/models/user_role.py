from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class UserRole(Base):
    """Назначение роли пользователю."""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
