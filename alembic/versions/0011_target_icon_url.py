"""add target icon url

Revision ID: 0011_target_icon_url
Revises: 0010_target_rewrite_prompt
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_target_icon_url"
down_revision: str | None = "0010_target_rewrite_prompt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("targets", sa.Column("icon_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("targets", "icon_url")
