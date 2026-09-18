"""add users, roles and permissions foundation

Revision ID: 0014_rbac_foundation
Revises: 0013_collection_scheduler
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_rbac_foundation"
down_revision: str | None = "0013_collection_scheduler"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PERMISSIONS = (
    (
        "overview.read",
        "Просмотр обзора",
        "Просмотр общей статистики и состояния приложения.",
    ),
    (
        "queue.read",
        "Просмотр очереди",
        "Просмотр материалов редакционной очереди.",
    ),
    (
        "queue.edit",
        "Редактирование материалов",
        "Изменение текста и параметров материала.",
    ),
    (
        "queue.rewrite",
        "Запуск рерайта",
        "Создание новой версии текста через LLM.",
    ),
    (
        "queue.submit",
        "Отправка на модерацию",
        "Передача подготовленного материала выпускающему редактору.",
    ),
    (
        "queue.moderate",
        "Модерация материалов",
        "Одобрение и отклонение подготовленных материалов.",
    ),
    (
        "queue.schedule",
        "Планирование публикаций",
        "Назначение и изменение времени публикации.",
    ),
    (
        "queue.publish",
        "Публикация материалов",
        "Немедленная публикация одобренных материалов.",
    ),
    (
        "collection.run",
        "Ручной сбор",
        "Запуск внеочередного сбора публикаций из источников.",
    ),
    (
        "scheduler.read",
        "Просмотр планировщика",
        "Просмотр расписания и истории автоматического сбора.",
    ),
    (
        "scheduler.manage",
        "Настройка планировщика",
        "Изменение расписания автоматического сбора.",
    ),
    (
        "sources.read",
        "Просмотр источников",
        "Просмотр подключённых источников публикаций.",
    ),
    (
        "sources.manage",
        "Управление источниками",
        "Создание, изменение и отключение источников.",
    ),
    (
        "targets.read",
        "Просмотр каналов",
        "Просмотр целевых каналов публикации.",
    ),
    (
        "targets.manage",
        "Управление каналами",
        "Создание, изменение и отключение целевых каналов.",
    ),
    (
        "users.read",
        "Просмотр пользователей",
        "Просмотр учётных записей пользователей.",
    ),
    (
        "users.manage",
        "Управление пользователями",
        "Создание, изменение и блокировка пользователей.",
    ),
    (
        "roles.read",
        "Просмотр ролей",
        "Просмотр ролей и назначенных им разрешений.",
    ),
    (
        "roles.manage",
        "Управление ролями",
        "Создание ролей и изменение назначенных им разрешений.",
    ),
    (
        "audit.read",
        "Просмотр аудита",
        "Просмотр журнала действий пользователей и системы.",
    ),
)

READ_ONLY_PERMISSIONS = {
    "overview.read",
    "queue.read",
    "scheduler.read",
    "sources.read",
    "targets.read",
}
EDITOR_PERMISSIONS = READ_ONLY_PERMISSIONS | {
    "queue.edit",
    "queue.rewrite",
    "queue.submit",
    "collection.run",
}
PUBLISHER_PERMISSIONS = EDITOR_PERMISSIONS | {
    "queue.moderate",
    "queue.schedule",
    "queue.publish",
}
ALL_PERMISSIONS = {code for code, _name, _description in PERMISSIONS}

ROLES = (
    (
        "administrator",
        "Администратор",
        "Полное управление приложением, пользователями и настройками.",
        ALL_PERMISSIONS,
    ),
    (
        "editor",
        "Редактор",
        "Подготовка материалов и отправка их на модерацию.",
        EDITOR_PERMISSIONS,
    ),
    (
        "publisher",
        "Выпускающий редактор",
        "Модерация, планирование и публикация материалов.",
        PUBLISHER_PERMISSIONS,
    ),
    (
        "viewer",
        "Наблюдатель",
        "Просмотр очереди, справочников и состояния планировщика.",
        READ_ONLY_PERMISSIONS,
    ),
)


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("permission_id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("role_id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("username_normalized", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("avatar_storage_key", sa.String(length=512), nullable=True),
        sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
            "length(display_name) BETWEEN 1 AND 200",
            name=op.f("ck_users_display_name_length"),
        ),
        sa.CheckConstraint(
            "length(username_normalized) BETWEEN 3 AND 64",
            name=op.f("ck_users_username_normalized_length"),
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
        sa.UniqueConstraint(
            "username_normalized",
            name=op.f("uq_users_username_normalized"),
        ),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.permission_id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.role_id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_id",
            name=op.f("pk_role_permissions"),
        ),
    )
    op.create_index(
        op.f("ix_role_permissions_permission_id"),
        "role_permissions",
        ["permission_id"],
        unique=False,
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.role_id"],
            name=op.f("fk_user_roles_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )
    op.create_index(
        op.f("ix_user_roles_role_id"),
        "user_roles",
        ["role_id"],
        unique=False,
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("permission_id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )
    roles_table = sa.table(
        "roles",
        sa.column("role_id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        permissions_table,
        [
            {"code": code, "name": name, "description": description}
            for code, name, description in PERMISSIONS
        ],
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "code": code,
                "name": name,
                "description": description,
                "is_system": True,
                "is_active": True,
            }
            for code, name, description, _permissions in ROLES
        ],
    )

    assignments_sql = ",\n            ".join(
        f"('{role_code}', '{permission_code}')"
        for role_code, _name, _description, permissions in ROLES
        for permission_code in sorted(permissions)
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT roles.role_id, permissions.permission_id
            FROM (VALUES
                {assignments_sql}
            ) AS assignments(role_code, permission_code)
            JOIN roles ON roles.code = assignments.role_code
            JOIN permissions ON permissions.code = assignments.permission_code
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(
        op.f("ix_role_permissions_permission_id"),
        table_name="role_permissions",
    )
    op.drop_table("role_permissions")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("permissions")
