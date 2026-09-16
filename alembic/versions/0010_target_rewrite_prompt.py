"""Добавляет индивидуальный промпт рерайта для целевого канала.

Revision ID: 0010_target_rewrite_prompt
Revises: 0009_queue_published_status
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_target_rewrite_prompt"
down_revision: str | Sequence[str] | None = "0009_queue_published_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("targets", sa.Column("rewrite_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("targets", "rewrite_prompt")
