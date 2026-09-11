"""Перестраивает очередь вокруг целевого канала.

Revision ID: 0005_target_centric_queue
Revises: 0004_create_post_queue
Create Date: 2026-09-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_target_centric_queue"
down_revision: str | Sequence[str] | None = "0004_create_post_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет связи целей с источниками и отдельную редакционную очередь."""

    op.create_table(
        "target_sources",
        sa.Column("target_source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "rewrite_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.target_id"],
            name=op.f("fk_target_sources_target_id_targets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.source_id"],
            name=op.f("fk_target_sources_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "target_source_id",
            name=op.f("pk_target_sources"),
        ),
        sa.UniqueConstraint(
            "target_id",
            "source_id",
            name="uq_target_sources_target_id_source_id",
        ),
    )
    op.create_index(
        op.f("ix_target_sources_target_id"),
        "target_sources",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_target_sources_source_id"),
        "target_sources",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_target_sources_target_id_is_active",
        "target_sources",
        ["target_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "queue_items",
        sa.Column("queue_item_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("rewritten_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "rewriting",
                "awaiting_moderation",
                "approved",
                "rejected",
                "scheduled",
                "failed",
                name="queue_item_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.post_id"],
            name=op.f("fk_queue_items_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.target_id"],
            name=op.f("fk_queue_items_target_id_targets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("queue_item_id", name=op.f("pk_queue_items")),
        sa.UniqueConstraint(
            "post_id",
            "target_id",
            name="uq_queue_items_post_id_target_id",
        ),
    )
    op.create_index(
        op.f("ix_queue_items_post_id"),
        "queue_items",
        ["post_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_items_target_id"),
        "queue_items",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        "ix_queue_items_target_id_status",
        "queue_items",
        ["target_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_queue_items_status_scheduled_at",
        "queue_items",
        ["status", "scheduled_at"],
        unique=False,
    )

    # Сохраняем уже существующие публикации: для каждой пары post/target
    # создаём редакционный QueueItem и переносим туда результат рерайта.
    op.execute(
        """
        INSERT INTO queue_items (
            post_id,
            target_id,
            rewritten_text,
            status,
            created_at,
            updated_at,
            error_message
        )
        SELECT
            p.post_id,
            pub.target_id,
            p.rewritten_text,
            CASE p.status
                WHEN 'rewriting' THEN 'rewriting'
                WHEN 'rewritten' THEN 'awaiting_moderation'
                WHEN 'awaiting_moderation' THEN 'awaiting_moderation'
                WHEN 'approved' THEN 'approved'
                WHEN 'rejected' THEN 'rejected'
                WHEN 'failed' THEN 'failed'
                ELSE 'pending'
            END,
            pub.created_at,
            pub.updated_at,
            p.error_message
        FROM publications AS pub
        JOIN posts AS p ON p.post_id = pub.post_id
        """
    )

    op.add_column(
        "publications",
        sa.Column("queue_item_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE publications AS pub
        SET queue_item_id = qi.queue_item_id
        FROM queue_items AS qi
        WHERE qi.post_id = pub.post_id
          AND qi.target_id = pub.target_id
        """
    )
    op.alter_column("publications", "queue_item_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_publications_queue_item_id_queue_items"),
        "publications",
        "queue_items",
        ["queue_item_id"],
        ["queue_item_id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_publications_queue_item_id",
        "publications",
        ["queue_item_id"],
    )
    op.create_index(
        op.f("ix_publications_queue_item_id"),
        "publications",
        ["queue_item_id"],
        unique=False,
    )

    op.drop_constraint(
        "uq_publications_post_id_target_id",
        "publications",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_publications_post_id_posts"),
        "publications",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_publications_target_id_targets"),
        "publications",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_publications_post_id"), table_name="publications")
    op.drop_index(op.f("ix_publications_target_id"), table_name="publications")
    op.drop_column("publications", "post_id")
    op.drop_column("publications", "target_id")

    # Post теперь описывает только получение исходного материала.
    op.drop_constraint("post_status", "posts", type_="check")
    op.execute(
        """
        UPDATE posts
        SET status = CASE
            WHEN status = 'failed' THEN 'failed'
            WHEN status = 'received' THEN 'received'
            ELSE 'processed'
        END
        """
    )
    op.create_check_constraint(
        "post_status",
        "posts",
        "status IN ('received', 'processed', 'failed')",
    )
    op.drop_column("posts", "rewritten_text")


def downgrade() -> None:
    """Возвращает прежнюю модель постов и публикаций."""

    op.add_column("posts", sa.Column("rewritten_text", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE posts AS p
        SET rewritten_text = qi.rewritten_text
        FROM queue_items AS qi
        WHERE qi.queue_item_id = (
            SELECT MIN(qi2.queue_item_id)
            FROM queue_items AS qi2
            WHERE qi2.post_id = p.post_id
        )
        """
    )

    op.drop_constraint("post_status", "posts", type_="check")
    op.execute(
        """
        UPDATE posts
        SET status = CASE
            WHEN status = 'processed' THEN 'rewritten'
            ELSE status
        END
        """
    )
    op.create_check_constraint(
        "post_status",
        "posts",
        "status IN ("
        "'received', 'rewriting', 'rewritten', 'awaiting_moderation', "
        "'approved', 'rejected', 'failed'"
        ")",
    )

    op.add_column("publications", sa.Column("post_id", sa.Integer(), nullable=True))
    op.add_column("publications", sa.Column("target_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE publications AS pub
        SET post_id = qi.post_id,
            target_id = qi.target_id
        FROM queue_items AS qi
        WHERE qi.queue_item_id = pub.queue_item_id
        """
    )
    op.alter_column("publications", "post_id", nullable=False)
    op.alter_column("publications", "target_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_publications_post_id_posts"),
        "publications",
        "posts",
        ["post_id"],
        ["post_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_publications_target_id_targets"),
        "publications",
        "targets",
        ["target_id"],
        ["target_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_publications_post_id_target_id",
        "publications",
        ["post_id", "target_id"],
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

    op.drop_index(op.f("ix_publications_queue_item_id"), table_name="publications")
    op.drop_constraint(
        "uq_publications_queue_item_id",
        "publications",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_publications_queue_item_id_queue_items"),
        "publications",
        type_="foreignkey",
    )
    op.drop_column("publications", "queue_item_id")

    op.drop_index("ix_queue_items_status_scheduled_at", table_name="queue_items")
    op.drop_index("ix_queue_items_target_id_status", table_name="queue_items")
    op.drop_index(op.f("ix_queue_items_target_id"), table_name="queue_items")
    op.drop_index(op.f("ix_queue_items_post_id"), table_name="queue_items")
    op.drop_table("queue_items")

    op.drop_index(
        "ix_target_sources_target_id_is_active",
        table_name="target_sources",
    )
    op.drop_index(op.f("ix_target_sources_source_id"), table_name="target_sources")
    op.drop_index(op.f("ix_target_sources_target_id"), table_name="target_sources")
    op.drop_table("target_sources")
