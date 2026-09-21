"""expand login attempt request id to match observability contract

Revision ID: 0016_login_attempt_request_id
Revises: 0015_auth_sessions
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_login_attempt_request_id"
down_revision: str | None = "0015_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "login_attempts",
        "request_id",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "login_attempts",
        "request_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=True,
        postgresql_using="left(request_id, 32)",
    )
