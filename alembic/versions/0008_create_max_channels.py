"""create max channels

Revision ID: 0008_create_max_channels
Revises: 0007_signatures
Create Date: 2026-09-13
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_create_max_channels"
down_revision = "0007_signatures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "max_channels",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("link", sa.String(length=2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_event_type", sa.String(length=64), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chat_id"),
    )
    op.create_index("ix_max_channels_link", "max_channels", ["link"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_max_channels_link", table_name="max_channels")
    op.drop_table("max_channels")
