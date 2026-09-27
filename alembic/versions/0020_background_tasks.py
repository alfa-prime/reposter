"""durable background tasks and outbox

Revision ID: 0020_background_tasks
Revises: 0019_journal_pagination
Create Date: 2026-09-27 23:26:30.356731

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_background_tasks"
down_revision: str | Sequence[str] | None = "0019_journal_pagination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет изменения схемы базы данных."""

    op.execute("SET LOCAL lock_timeout = '2s'")
    op.execute("SET LOCAL statement_timeout = '30s'")
    op.create_table(
        "background_tasks",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column(
            "queue",
            sa.Enum(
                "rewrite",
                "collection",
                "publication",
                "maintenance",
                name="background_task_queue",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.Enum(
                "pending",
                "running",
                "retry_wait",
                "succeeded",
                "failed",
                "cancelled",
                "needs_review",
                name="background_task_state",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("task_id", name=op.f("pk_background_tasks")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_background_tasks_idempotency_key")
        ),
    )
    op.create_index(
        "ix_background_tasks_lease",
        "background_tasks",
        ["state", "lease_until"],
        unique=False,
    )
    op.create_index(
        "ix_background_tasks_ready",
        "background_tasks",
        ["queue", "state", "available_at"],
        unique=False,
    )
    op.create_index(
        "uq_background_tasks_active_subject",
        "background_tasks",
        ["queue", "subject_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending', 'running', 'retry_wait') AND subject_id IS NOT NULL"
        ),
    )
    op.create_table(
        "task_deliveries",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["background_tasks.task_id"],
            name=op.f("fk_task_deliveries_task_id_background_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", name=op.f("pk_task_deliveries")),
    )
    op.create_table(
        "task_outbox",
        sa.Column("outbox_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("queue", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["background_tasks.task_id"],
            name=op.f("fk_task_outbox_task_id_background_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("outbox_id", name=op.f("pk_task_outbox")),
        sa.UniqueConstraint("task_id", name=op.f("uq_task_outbox_task_id")),
    )
    op.create_index(
        "ix_task_outbox_dispatch",
        "task_outbox",
        ["delivered_at", "available_at"],
        unique=False,
    )
    op.add_column(
        "collection_runs", sa.Column("background_task_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        op.f("ix_collection_runs_background_task_id"),
        "collection_runs",
        ["background_task_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_collection_runs_background_task_id_background_tasks"),
        "collection_runs",
        "background_tasks",
        ["background_task_id"],
        ["task_id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "publication_attempts",
        sa.Column("background_task_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_publication_attempts_background_task_id"),
        "publication_attempts",
        ["background_task_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_publication_attempts_background_task_id_background_tasks"),
        "publication_attempts",
        "background_tasks",
        ["background_task_id"],
        ["task_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Отменяет изменения схемы базы данных."""

    op.execute("SET LOCAL lock_timeout = '2s'")
    op.execute("SET LOCAL statement_timeout = '30s'")
    op.drop_constraint(
        op.f("fk_publication_attempts_background_task_id_background_tasks"),
        "publication_attempts",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_publication_attempts_background_task_id"),
        table_name="publication_attempts",
    )
    op.drop_column("publication_attempts", "background_task_id")
    op.drop_constraint(
        op.f("fk_collection_runs_background_task_id_background_tasks"),
        "collection_runs",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_collection_runs_background_task_id"), table_name="collection_runs"
    )
    op.drop_column("collection_runs", "background_task_id")
    op.drop_index("ix_task_outbox_dispatch", table_name="task_outbox")
    op.drop_table("task_outbox")
    op.drop_table("task_deliveries")
    op.drop_index(
        "uq_background_tasks_active_subject",
        table_name="background_tasks",
        postgresql_where=sa.text(
            "state IN ('pending', 'running', 'retry_wait') AND subject_id IS NOT NULL"
        ),
    )
    op.drop_index("ix_background_tasks_ready", table_name="background_tasks")
    op.drop_index("ix_background_tasks_lease", table_name="background_tasks")
    op.drop_table("background_tasks")
