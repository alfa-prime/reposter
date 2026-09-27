"""Index journal filters and store an independent historical channel snapshot.

Revision ID: 0019_journal_pagination
Revises: 0018_publication_recovery
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_journal_pagination"
down_revision: str | None = "0018_publication_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_INDEXES = {
    "ix_audit_events_subject_page": ["subject_type", "created_at", "audit_event_id"],
    "ix_audit_events_actor_page": [
        "subject_type",
        "actor_user_id",
        "created_at",
        "audit_event_id",
    ],
    "ix_audit_events_action_page": [
        "subject_type",
        "action",
        "created_at",
        "audit_event_id",
    ],
    "ix_audit_events_material_page": [
        "subject_type",
        "subject_id",
        "created_at",
        "audit_event_id",
    ],
    "ix_audit_events_target_page": [
        "subject_type",
        "target_id",
        "created_at",
        "audit_event_id",
    ],
}
RUN_INDEXES = {
    "ix_collection_runs_status_page": ["status", "collection_run_id"],
    "ix_collection_runs_trigger_page": ["trigger", "collection_run_id"],
    "ix_collection_runs_status_trigger_page": [
        "status",
        "trigger",
        "collection_run_id",
    ],
}


def upgrade() -> None:
    # Fail atomically rather than wait indefinitely for production table locks.
    op.execute("SET LOCAL lock_timeout = '2s'")
    op.execute("SET LOCAL statement_timeout = '30s'")
    # Generated snapshot stays correct for old and new application writers.
    # Nested CASE also tolerates malformed historical JSON and integer overflow.
    op.add_column(
        "audit_events",
        sa.Column(
            "target_id",
            sa.Integer(),
            sa.Computed(
                "CASE WHEN subject_type = 'queue_item' AND details->>'target_id' ~ '^[0-9]{1,10}$' THEN CASE WHEN (details->>'target_id')::bigint BETWEEN 1 AND 2147483647 THEN (details->>'target_id')::integer END END",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    for name, columns in AUDIT_INDEXES.items():
        op.create_index(name, "audit_events", columns)
    for name, columns in RUN_INDEXES.items():
        op.create_index(name, "collection_runs", columns)


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '2s'")
    op.execute("SET LOCAL statement_timeout = '30s'")
    for name in reversed(RUN_INDEXES):
        op.drop_index(name, table_name="collection_runs")
    for name in reversed(AUDIT_INDEXES):
        op.drop_index(name, table_name="audit_events")
    op.drop_column("audit_events", "target_id")
