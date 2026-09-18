"""Аутентификация и управление доступом."""

from news_reposter.auth.identity import (
    IdentityValidationError,
    PreparedUsername,
    prepare_display_name,
    prepare_username,
)
from news_reposter.auth.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordManager,
    PasswordValidationError,
    validate_password,
)
from news_reposter.auth.rbac import (
    PERMISSIONS,
    SYSTEM_ROLES,
    PermissionCode,
    PermissionDefinition,
    SystemRoleCode,
    SystemRoleDefinition,
)

__all__ = [
    "IdentityValidationError",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "PERMISSIONS",
    "PasswordManager",
    "PasswordValidationError",
    "PermissionCode",
    "PermissionDefinition",
    "PreparedUsername",
    "SYSTEM_ROLES",
    "SystemRoleCode",
    "SystemRoleDefinition",
    "prepare_display_name",
    "prepare_username",
    "validate_password",
]
