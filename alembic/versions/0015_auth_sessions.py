"""add server-side sessions and login attempts

Revision ID: 0015_auth_sessions
Revises: 0014_rbac_foundation
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_auth_sessions"
down_revision: str | None = "0014_rbac_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "absolute_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.CheckConstraint(
            "absolute_expires_at > created_at",
            name=op.f("ck_user_sessions_expires_after_created"),
        ),
        sa.CheckConstraint(
            "octet_length(csrf_token_hash) = 32",
            name=op.f("ck_user_sessions_csrf_token_hash_length"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_user_sessions_revoked_after_created"),
        ),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32",
            name=op.f("ck_user_sessions_token_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint(
            "token_hash",
            name=op.f("uq_user_sessions_token_hash"),
        ),
    )
    op.create_index(
        op.f("ix_user_sessions_absolute_expires_at"),
        "user_sessions",
        ["absolute_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_sessions_user_active",
        "user_sessions",
        ["user_id", "revoked_at", "absolute_expires_at"],
        unique=False,
    )

    op.create_table(
        "login_attempts",
        sa.Column("login_attempt_id", sa.Integer(), nullable=False),
        sa.Column(
            "username_fingerprint",
            sa.LargeBinary(length=32),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("was_successful", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "octet_length(username_fingerprint) = 32",
            name=op.f("ck_login_attempts_username_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_login_attempts_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "login_attempt_id",
            name=op.f("pk_login_attempts"),
        ),
    )
    op.create_index(
        op.f("ix_login_attempts_attempted_at"),
        "login_attempts",
        ["attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_login_attempts_ip_at",
        "login_attempts",
        ["ip_address", "attempted_at"],
        unique=False,
        postgresql_where=sa.text("was_successful = false"),
    )
    op.create_index(
        op.f("ix_login_attempts_user_id"),
        "login_attempts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_login_attempts_username_at",
        "login_attempts",
        ["username_fingerprint", "attempted_at"],
        unique=False,
        postgresql_where=sa.text("was_successful = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_login_attempts_username_at",
        table_name="login_attempts",
    )
    op.drop_index(
        op.f("ix_login_attempts_user_id"),
        table_name="login_attempts",
    )
    op.drop_index("ix_login_attempts_ip_at", table_name="login_attempts")
    op.drop_index(
        op.f("ix_login_attempts_attempted_at"),
        table_name="login_attempts",
    )
    op.drop_table("login_attempts")

    op.drop_index(
        "ix_user_sessions_user_active",
        table_name="user_sessions",
    )
    op.drop_index(
        op.f("ix_user_sessions_absolute_expires_at"),
        table_name="user_sessions",
    )
    op.drop_table("user_sessions")
