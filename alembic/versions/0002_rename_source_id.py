"""Переименовывает первичный ключ источника.

Revision ID: 0002_rename_source_id
Revises: 0001_create_sources
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_rename_source_id"
down_revision: str | Sequence[str] | None = "0001_create_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Переименовывает id в source_id без потери данных."""

    op.alter_column("sources", "id", new_column_name="source_id")


def downgrade() -> None:
    """Возвращает первичному ключу прежнее имя."""

    op.alter_column("sources", "source_id", new_column_name="id")
