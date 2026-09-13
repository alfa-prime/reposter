"""Добавляет статус published для элементов редакционной очереди.

Revision ID: 0009_queue_published_status
Revises: 0008_create_max_channels
Create Date: 2026-09-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_queue_published_status"
down_revision: str | Sequence[str] | None = "0008_create_max_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_VALUES = (
    "pending",
    "rewriting",
    "awaiting_moderation",
    "approved",
    "rejected",
    "scheduled",
    "failed",
)
NEW_VALUES = (*OLD_VALUES[:-1], "published", OLD_VALUES[-1])


def _constraint(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"status IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint("queue_item_status", "queue_items", type_="check")
    op.create_check_constraint(
        "queue_item_status",
        "queue_items",
        _constraint(NEW_VALUES),
    )


def downgrade() -> None:
    op.execute("UPDATE queue_items SET status = 'approved' WHERE status = 'published'")
    op.drop_constraint("queue_item_status", "queue_items", type_="check")
    op.create_check_constraint(
        "queue_item_status",
        "queue_items",
        _constraint(OLD_VALUES),
    )
