"""add source icon url

Revision ID: 0012_source_icon_url
Revises: 0011_target_icon_url
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_source_icon_url"
down_revision: str | None = "0011_target_icon_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources", sa.Column("icon_url", sa.String(length=2048), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sources", "icon_url")
