"""add channel and publication signatures

Revision ID: 0007_signatures
Revises: 0006_source_delete_cascade
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_signatures"
down_revision = "0006_source_delete_cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("targets", sa.Column("default_signature", sa.Text(), nullable=True))
    op.add_column("queue_items", sa.Column("signature_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("queue_items", "signature_text")
    op.drop_column("targets", "default_signature")
