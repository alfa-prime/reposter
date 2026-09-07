"""Создаёт таблицу целей публикаций.

Revision ID: 0003_create_targets
Revises: 0002_rename_source_id
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_create_targets"
down_revision: str | Sequence[str] | None = "0002_rename_source_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу целей и индекс для выборки активных."""

    op.create_table(
        "targets",
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
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
        sa.PrimaryKeyConstraint("target_id", name=op.f("pk_targets")),
        sa.UniqueConstraint(
            "platform",
            "external_id",
            name="uq_targets_platform_external_id",
        ),
    )
    op.create_index(
        "ix_targets_platform_is_active",
        "targets",
        ["platform", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет таблицу целей публикаций."""

    op.drop_index("ix_targets_platform_is_active", table_name="targets")
    op.drop_table("targets")
