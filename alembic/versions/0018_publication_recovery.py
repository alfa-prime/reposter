"""Добавляет неопределённый результат публикации и историю попыток.

Revision ID: 0018_publication_recovery
Revises: 0017_user_target_access
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_publication_recovery"
down_revision: str | Sequence[str] | None = "0017_user_target_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _constraint(values: tuple[str, ...]) -> str:
    return "status IN (" + ", ".join(f"'{value}'" for value in values) + ")"


QUEUE_OLD = (
    "pending",
    "rewriting",
    "awaiting_moderation",
    "approved",
    "rejected",
    "scheduled",
    "published",
    "failed",
)
QUEUE_NEW = (*QUEUE_OLD, "publication_unknown")
PUBLICATION_OLD = ("pending", "publishing", "published", "failed")
PUBLICATION_NEW = (*PUBLICATION_OLD, "unknown")


def upgrade() -> None:
    op.drop_constraint("queue_item_status", "queue_items", type_="check")
    op.create_check_constraint(
        "queue_item_status", "queue_items", _constraint(QUEUE_NEW)
    )
    op.drop_constraint("publication_status", "publications", type_="check")
    op.create_check_constraint(
        "publication_status", "publications", _constraint(PUBLICATION_NEW)
    )
    op.create_table(
        "publication_attempts",
        sa.Column("publication_attempt_id", sa.Integer(), primary_key=True),
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey("publications.publication_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "sending",
                "confirmed",
                "failed",
                "unknown",
                name="publication_attempt_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column(
            "initiated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
        ),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("prepared_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("check_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("external_message_id", sa.String(255)),
        sa.Column("publication_url", sa.String(2048)),
        sa.Column("error_type", sa.String(100)),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_publication_attempts_publication_started",
        "publication_attempts",
        ["publication_id", "started_at"],
    )
    op.create_index(
        "ix_publication_attempts_status_started",
        "publication_attempts",
        ["status", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("publication_attempts")
    op.execute(
        "UPDATE queue_items SET status = 'failed' WHERE status = 'publication_unknown'"
    )
    op.execute("UPDATE publications SET status = 'failed' WHERE status = 'unknown'")
    op.drop_constraint("queue_item_status", "queue_items", type_="check")
    op.create_check_constraint(
        "queue_item_status", "queue_items", _constraint(QUEUE_OLD)
    )
    op.drop_constraint("publication_status", "publications", type_="check")
    op.create_check_constraint(
        "publication_status", "publications", _constraint(PUBLICATION_OLD)
    )
