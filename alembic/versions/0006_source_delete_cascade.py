"""Cascade source deletion through collected posts.

Revision ID: 0006_source_delete_cascade
Revises: 0005_target_centric_queue
"""

from alembic import op

revision = "0006_source_delete_cascade"
down_revision = "0005_target_centric_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_posts_source_id_sources",
        "posts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_posts_source_id_sources",
        "posts",
        "sources",
        ["source_id"],
        ["source_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_posts_source_id_sources",
        "posts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_posts_source_id_sources",
        "posts",
        "sources",
        ["source_id"],
        ["source_id"],
        ondelete="RESTRICT",
    )
