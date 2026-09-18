from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from news_reposter.db.base import Base


class RolePermission(Base):
    """Связь роли с разрешённым ей действием."""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.permission_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
