import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from news_reposter.api.v1.queue_permissions import (
    can_access_target,
    get_accessible_queue_item,
    target_scope,
)
from news_reposter.auth.context import AuthContext
from news_reposter.db.models import Permission, Role, Target, User, UserSession
from news_reposter.schemas.admin import AdminUserCreate


def _context(role_code: str, targets: list[Target]) -> AuthContext:
    role = Role(
        role_id=1,
        code=role_code,
        name=role_code,
        is_active=True,
        permissions=[Permission(code="queue.read", name="Просмотр")],
    )
    user = User(
        user_id=1,
        username="editor",
        username_normalized="editor",
        display_name="Редактор",
        password_hash="hash",
        roles=[role],
        targets=targets,
    )
    return AuthContext.from_session(UserSession(user=user))


def test_administrator_has_global_target_access() -> None:
    context = _context("administrator", [])

    assert context.target_ids is None
    assert can_access_target(context, 999)
    assert target_scope(context) == {}


def test_editor_only_has_assigned_targets() -> None:
    context = _context(
        "editor",
        [Target(target_id=7, name="Канал", platform="max", external_id="7")],
    )

    assert context.target_ids == frozenset({7})
    assert can_access_target(context, 7)
    assert not can_access_target(context, 8)
    assert target_scope(context) == {"allowed_target_ids": frozenset({7})}


def test_queue_lookup_passes_user_target_scope_to_repository() -> None:
    async def scenario() -> None:
        repository = SimpleNamespace(get=AsyncMock(return_value=None))
        context = _context(
            "editor",
            [Target(target_id=7, name="Канал", platform="max", external_id="7")],
        )

        await get_accessible_queue_item(repository, 42, context)

        repository.get.assert_awaited_once_with(
            42,
            allowed_target_ids=frozenset({7}),
        )

    asyncio.run(scenario())


def test_new_user_has_no_targets_by_default_and_rejects_duplicates() -> None:
    payload = AdminUserCreate(
        username="editor",
        display_name="Редактор",
        temporary_password="temporary password 123",
        role_codes=["editor"],
    )
    assert payload.target_ids == []

    with pytest.raises(ValidationError):
        AdminUserCreate(
            username="editor",
            display_name="Редактор",
            temporary_password="temporary password 123",
            role_codes=["editor"],
            target_ids=[7, 7],
        )
