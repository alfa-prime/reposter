"""Создаёт таблицу источников.

Revision ID: 0001_create_sources
Revises:
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_sources"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу источников и индекс для выборки активных."""

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint("url", name=op.f("uq_sources_url")),
    )
    op.create_index(
        "ix_sources_platform_is_active",
        "sources",
        ["platform", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет таблицу источников."""

    op.drop_index("ix_sources_platform_is_active", table_name="sources")
    op.drop_table("sources")
