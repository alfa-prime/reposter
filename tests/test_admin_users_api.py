from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from news_reposter.api.dependencies import get_current_auth, get_user_service
from news_reposter.auth.rbac import PermissionCode
from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import get_settings
from news_reposter.db.models import Permission, Role, User
from news_reposter.main import app

CSRF_TOKEN = "admin-users-csrf-token"
CSRF_COOKIE_NAME = get_settings().auth_csrf_cookie_name


def make_role(code: str = "editor", name: str = "Редактор") -> Role:
    return Role(
        role_id=2,
        code=code,
        name=name,
        description="Работа с материалами",
        is_system=True,
        is_active=True,
        permissions=[Permission(code="queue.read", name="Просмотр", description="")],
    )


def make_user(user_id: int = 2) -> User:
    now = datetime.now(UTC)
    return User(
        user_id=user_id,
        username="editor",
        username_normalized="editor",
        display_name="Редактор",
        password_hash="hash",
        is_active=True,
        must_change_password=True,
        created_at=now,
        updated_at=now,
        roles=[make_role()],
    )


class MemoryUserService:
    def __init__(self) -> None:
        self.user = make_user()
        self.role = self.user.roles[0]
        self.revoked = 0

    async def list_users(self) -> list[User]:
        return [self.user]

    async def list_roles(self) -> list[Role]:
        return [self.role]

    async def create_user(self, **data: object) -> User:
        self.user.username = str(data["username"])
        self.user.username_normalized = self.user.username.casefold()
        self.user.display_name = str(data["display_name"])
        return self.user

    async def update_user(self, _user_id: int, **data: object) -> User:
        if "display_name" in data:
            self.user.display_name = str(data["display_name"])
        if "is_active" in data:
            self.user.is_active = bool(data["is_active"])
        return self.user

    async def reset_password(self, _user_id: int, **_data: object) -> User:
        self.user.must_change_password = True
        return self.user

    async def revoke_sessions(self, _user_id: int, **_data: object) -> int:
        self.revoked = 3
        return self.revoked


@pytest.fixture
def admin_user_api() -> Iterator[MemoryUserService]:
    service = MemoryUserService()

    async def authenticated() -> SimpleNamespace:
        return SimpleNamespace(
            user=SimpleNamespace(user_id=1, must_change_password=False),
            session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
            permission_codes=frozenset(
                {
                    PermissionCode.USERS_READ.value,
                    PermissionCode.USERS_MANAGE.value,
                    PermissionCode.ROLES_READ.value,
                }
            ),
        )

    app.dependency_overrides[get_current_auth] = authenticated
    app.dependency_overrides[get_user_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_current_auth, None)
        app.dependency_overrides.pop(get_user_service, None)


def test_admin_users_full_http_flow(admin_user_api: MemoryUserService) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
        ) as client:
            listed = await client.get("/api/v1/admin/users")
            roles = await client.get("/api/v1/admin/roles")
            created = await client.post(
                "/api/v1/admin/users",
                json={
                    "username": "publisher",
                    "display_name": "Выпускающий",
                    "temporary_password": "temporary password 123",
                    "role_codes": ["editor"],
                },
            )
            updated = await client.patch(
                "/api/v1/admin/users/2",
                json={"display_name": "Старший редактор"},
            )
            reset = await client.post(
                "/api/v1/admin/users/2/reset-password",
                json={"temporary_password": "another temporary password"},
            )
            revoked = await client.post("/api/v1/admin/users/2/revoke-sessions")

        assert listed.status_code == 200
        assert listed.json()[0]["roles"][0]["code"] == "editor"
        assert roles.status_code == 200
        assert roles.json()[0]["permissions"] == ["queue.read"]
        assert created.status_code == 201
        assert created.json()["username"] == "publisher"
        assert updated.status_code == 200
        assert updated.json()["display_name"] == "Старший редактор"
        assert reset.status_code == 200
        assert reset.json()["must_change_password"] is True
        assert revoked.json() == {"revoked_sessions": 3}

    asyncio.run(scenario())


def test_admin_users_permissions_and_csrf(admin_user_api: MemoryUserService) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
        ) as client:
            missing_csrf = await client.patch(
                "/api/v1/admin/users/2",
                json={"display_name": "Новое имя"},
            )

            app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
                user=SimpleNamespace(user_id=1, must_change_password=False),
                session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
                permission_codes=frozenset({PermissionCode.QUEUE_READ.value}),
            )
            forbidden = await client.get("/api/v1/admin/users")

        assert missing_csrf.status_code == 403
        assert missing_csrf.json() == {"detail": "Недействительный CSRF-токен"}
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": "Недостаточно прав"}

    asyncio.run(scenario())
