"""Создаёт таблицы постов, вложений и публикаций.

Revision ID: 0004_create_post_queue
Revises: 0003_create_targets
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_create_post_queue"
down_revision: str | Sequence[str] | None = "0003_create_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт связанные таблицы очереди обработки и публикации."""

    op.create_table(
        "posts",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_post_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("original_text", sa.Text(), server_default="", nullable=False),
        sa.Column("rewritten_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "received",
                "rewriting",
                "rewritten",
                "awaiting_moderation",
                "approved",
                "rejected",
                "failed",
                name="post_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="received",
            nullable=False,
        ),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.source_id"],
            name=op.f("fk_posts_source_id_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("post_id", name=op.f("pk_posts")),
        sa.UniqueConstraint(
            "source_id",
            "external_post_id",
            name="uq_posts_source_id_external_post_id",
        ),
    )
    op.create_index(
        "ix_posts_source_id_status",
        "posts",
        ["source_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_posts_status_received_at",
        "posts",
        ["status", "received_at"],
        unique=False,
    )

    op.create_table(
        "post_attachments",
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column(
            "attachment_type",
            sa.Enum(
                "photo",
                "video",
                "audio",
                "document",
                "link",
                "other",
                name="attachment_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("external_attachment_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_post_attachments_position",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.post_id"],
            name=op.f("fk_post_attachments_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attachment_id", name=op.f("pk_post_attachments")),
        sa.UniqueConstraint(
            "post_id",
            "position",
            name="uq_post_attachments_post_id_position",
        ),
    )
    op.create_index(
        op.f("ix_post_attachments_post_id"),
        "post_attachments",
        ["post_id"],
        unique=False,
    )

    op.create_table(
        "publications",
        sa.Column("publication_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "publishing",
                "published",
                "failed",
                name="publication_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("publication_url", sa.String(length=2048), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_publications_attempts"),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.post_id"],
            name=op.f("fk_publications_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.target_id"],
            name=op.f("fk_publications_target_id_targets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("publication_id", name=op.f("pk_publications")),
        sa.UniqueConstraint(
            "post_id",
            "target_id",
            name="uq_publications_post_id_target_id",
        ),
    )
    op.create_index(
        op.f("ix_publications_post_id"),
        "publications",
        ["post_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_publications_target_id"),
        "publications",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        "ix_publications_status_created_at",
        "publications",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет таблицы очереди в обратном порядке зависимостей."""

    op.drop_index("ix_publications_status_created_at", table_name="publications")
    op.drop_index(op.f("ix_publications_target_id"), table_name="publications")
    op.drop_index(op.f("ix_publications_post_id"), table_name="publications")
    op.drop_table("publications")
    op.drop_index(op.f("ix_post_attachments_post_id"), table_name="post_attachments")
    op.drop_table("post_attachments")
    op.drop_index("ix_posts_status_received_at", table_name="posts")
    op.drop_index("ix_posts_source_id_status", table_name="posts")
    op.drop_table("posts")
