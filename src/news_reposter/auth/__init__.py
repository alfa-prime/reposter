"""Аутентификация и управление доступом."""

from news_reposter.auth.rbac import (
    PERMISSIONS,
    SYSTEM_ROLES,
    PermissionCode,
    PermissionDefinition,
    SystemRoleCode,
    SystemRoleDefinition,
)

__all__ = [
    "PERMISSIONS",
    "PermissionCode",
    "PermissionDefinition",
    "SYSTEM_ROLES",
    "SystemRoleCode",
    "SystemRoleDefinition",
]
