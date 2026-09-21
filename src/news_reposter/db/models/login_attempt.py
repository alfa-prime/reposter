from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from news_reposter.db.base import Base
from news_reposter.db.models.types import IPAddress

if TYPE_CHECKING:
    from news_reposter.db.models.user import User


class LoginAttempt(Base):
    """Результат попытки входа для ограничения автоматического перебора."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        CheckConstraint(
            "octet_length(username_fingerprint) = 32",
            name="ck_login_attempts_username_fingerprint_length",
        ),
        Index(
            "ix_login_attempts_username_at",
            "username_fingerprint",
            "attempted_at",
            postgresql_where=text("was_successful = false"),
        ),
        Index(
            "ix_login_attempts_ip_at",
            "ip_address",
            "attempted_at",
            postgresql_where=text("was_successful = false"),
        ),
    )

    login_attempt_id: Mapped[int] = mapped_column(primary_key=True)
    username_fingerprint: Mapped[bytes] = mapped_column(
        LargeBinary(32),
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[IPAddress | None] = mapped_column(INET, nullable=True)
    was_successful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="login_attempts")
