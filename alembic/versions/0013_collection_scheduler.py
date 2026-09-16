"""add collection scheduler settings and history

Revision ID: 0013_collection_scheduler
Revises: 0012_source_icon_url
Create Date: 2026-09-16
"""

from collections.abc import Sequence
from datetime import time

import sqlalchemy as sa

from alembic import op

revision: str = "0013_collection_scheduler"
down_revision: str | None = "0012_source_icon_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_settings",
        sa.Column("collection_settings_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "collection_settings_id = 1",
            name=op.f("ck_collection_settings_singleton"),
        ),
        sa.CheckConstraint(
            "interval_minutes >= 1 AND interval_minutes <= 1440",
            name=op.f("ck_collection_settings_interval_minutes_range"),
        ),
        sa.CheckConstraint(
            "start_time <> end_time",
            name=op.f("ck_collection_settings_different_times"),
        ),
        sa.PrimaryKeyConstraint(
            "collection_settings_id",
            name=op.f("pk_collection_settings"),
        ),
    )
    op.bulk_insert(
        sa.table(
            "collection_settings",
            sa.column("collection_settings_id", sa.Integer()),
            sa.column("enabled", sa.Boolean()),
            sa.column("interval_minutes", sa.Integer()),
            sa.column("start_time", sa.Time()),
            sa.column("end_time", sa.Time()),
            sa.column("timezone", sa.String()),
        ),
        [
            {
                "collection_settings_id": 1,
                "enabled": False,
                "interval_minutes": 15,
                "start_time": time(hour=8),
                "end_time": time(hour=20),
                "timezone": "Europe/Moscow",
            }
        ],
    )

    op.create_table(
        "collection_runs",
        sa.Column("collection_run_id", sa.Integer(), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum(
                "manual",
                "scheduled",
                name="collection_run_trigger",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "success",
                "partial",
                "failed",
                "skipped",
                "interrupted",
                name="collection_run_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sources_checked", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "sources_succeeded", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("sources_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("posts_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("posts_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "queue_items_created", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("collection_run_id", name=op.f("pk_collection_runs")),
    )
    op.create_index(
        op.f("ix_collection_runs_started_at"),
        "collection_runs",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "collection_source_runs",
        sa.Column("collection_source_run_id", sa.Integer(), nullable=False),
        sa.Column("collection_run_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "success",
                "no_changes",
                "failed",
                "interrupted",
                name="collection_source_run_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_post_id_before", sa.String(length=255), nullable=True),
        sa.Column("last_post_id_after", sa.String(length=255), nullable=True),
        sa.Column("posts_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("posts_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "queue_items_created", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["collection_runs.collection_run_id"],
            name=op.f("fk_collection_source_runs_collection_run_id_collection_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.source_id"],
            name=op.f("fk_collection_source_runs_source_id_sources"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "collection_source_run_id",
            name=op.f("pk_collection_source_runs"),
        ),
    )
    op.create_index(
        op.f("ix_collection_source_runs_collection_run_id"),
        "collection_source_runs",
        ["collection_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_source_runs_source_id"),
        "collection_source_runs",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_collection_source_runs_source_id"),
        table_name="collection_source_runs",
    )
    op.drop_index(
        op.f("ix_collection_source_runs_collection_run_id"),
        table_name="collection_source_runs",
    )
    op.drop_table("collection_source_runs")
    op.drop_index(op.f("ix_collection_runs_started_at"), table_name="collection_runs")
    op.drop_table("collection_runs")
    op.drop_table("collection_settings")
