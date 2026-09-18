from sqlalchemy import Boolean, CheckConstraint, DateTime, String, inspect

from news_reposter.auth import (
    PERMISSIONS,
    SYSTEM_ROLES,
    PermissionCode,
    SystemRoleCode,
)
from news_reposter.db.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)


def constraint_names(model: type[object]) -> set[str | None]:
    return {constraint.name for constraint in model.__table__.constraints}


def test_permission_table_structure() -> None:
    table = Permission.__table__

    assert table.name == "permissions"
    assert table.c.permission_id.primary_key is True
    assert isinstance(table.c.code.type, String)
    assert table.c.code.type.length == 100
    assert table.c.code.nullable is False
    assert "uq_permissions_code" in constraint_names(Permission)
    assert isinstance(table.c.created_at.type, DateTime)


def test_role_table_structure() -> None:
    table = Role.__table__

    assert table.name == "roles"
    assert table.c.role_id.primary_key is True
    assert table.c.code.type.length == 64
    assert table.c.name.type.length == 100
    assert isinstance(table.c.is_system.type, Boolean)
    assert table.c.is_system.default.arg is False
    assert table.c.is_active.default.arg is True
    assert "uq_roles_code" in constraint_names(Role)
    assert "uq_roles_name" in constraint_names(Role)


def test_user_table_structure_includes_identity_and_avatar() -> None:
    table = User.__table__

    assert table.name == "users"
    assert table.c.user_id.primary_key is True
    assert table.c.username.type.length == 64
    assert table.c.username_normalized.type.length == 64
    assert table.c.display_name.type.length == 200
    assert table.c.password_hash.type.length == 255
    assert table.c.password_hash.nullable is False
    assert table.c.avatar_storage_key.type.length == 512
    assert table.c.avatar_storage_key.nullable is True
    assert isinstance(table.c.avatar_updated_at.type, DateTime)
    assert table.c.is_active.default.arg is True
    assert table.c.must_change_password.default.arg is True
    assert "uq_users_username_normalized" in constraint_names(User)
    assert (
        sum(isinstance(constraint, CheckConstraint) for constraint in table.constraints)
        == 2
    )


def test_role_permission_link_uses_composite_key_and_cascade() -> None:
    table = RolePermission.__table__

    assert {column.name for column in table.primary_key.columns} == {
        "role_id",
        "permission_id",
    }
    role_fk = next(iter(table.c.role_id.foreign_keys))
    permission_fk = next(iter(table.c.permission_id.foreign_keys))
    assert role_fk.target_fullname == "roles.role_id"
    assert role_fk.ondelete == "CASCADE"
    assert permission_fk.target_fullname == "permissions.permission_id"
    assert permission_fk.ondelete == "CASCADE"
    assert "ix_role_permissions_permission_id" in {
        index.name for index in table.indexes
    }


def test_user_role_link_supports_multiple_roles_and_cascade() -> None:
    table = UserRole.__table__

    assert {column.name for column in table.primary_key.columns} == {
        "user_id",
        "role_id",
    }
    user_fk = next(iter(table.c.user_id.foreign_keys))
    role_fk = next(iter(table.c.role_id.foreign_keys))
    assert user_fk.target_fullname == "users.user_id"
    assert user_fk.ondelete == "CASCADE"
    assert role_fk.target_fullname == "roles.role_id"
    assert role_fk.ondelete == "CASCADE"
    assert "ix_user_roles_role_id" in {index.name for index in table.indexes}


def test_rbac_relationships_are_bidirectional() -> None:
    permission_relationships = inspect(Permission).relationships
    role_relationships = inspect(Role).relationships
    user_relationships = inspect(User).relationships

    assert permission_relationships.roles.mapper.class_ is Role
    assert role_relationships.permissions.mapper.class_ is Permission
    assert role_relationships.users.mapper.class_ is User
    assert user_relationships.roles.mapper.class_ is Role


def test_permission_catalog_covers_every_backend_permission() -> None:
    assert set(PERMISSIONS) == set(PermissionCode)
    assert all(definition.name for definition in PERMISSIONS.values())
    assert all(definition.description for definition in PERMISSIONS.values())


def test_system_roles_reference_only_known_permissions() -> None:
    assert set(SYSTEM_ROLES) == set(SystemRoleCode)
    assert SYSTEM_ROLES[SystemRoleCode.ADMINISTRATOR].permissions == frozenset(
        PermissionCode
    )

    for role in SYSTEM_ROLES.values():
        assert role.name
        assert role.description
        assert role.permissions
        assert role.permissions <= frozenset(PermissionCode)


def test_system_role_privileges_are_monotonic() -> None:
    viewer = SYSTEM_ROLES[SystemRoleCode.VIEWER].permissions
    editor = SYSTEM_ROLES[SystemRoleCode.EDITOR].permissions
    publisher = SYSTEM_ROLES[SystemRoleCode.PUBLISHER].permissions
    administrator = SYSTEM_ROLES[SystemRoleCode.ADMINISTRATOR].permissions

    assert viewer < editor < publisher < administrator
