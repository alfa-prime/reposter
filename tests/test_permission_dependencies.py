import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated
from unittest.mock import AsyncMock

import httpx
from fastapi import Depends, FastAPI

from news_reposter.api.dependencies import (
    get_user_session_service,
    require_permission,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.db.models import Permission, Role, User, UserSession
from news_reposter.services.user_sessions import InvalidSessionError

SESSION_TOKEN = "permission-test-session"


def _user_session(
    *,
    permissions: set[PermissionCode],
    must_change_password: bool = False,
) -> UserSession:
    role = Role(
        code="test-role",
        name="Тестовая роль",
        is_active=True,
        permissions=[
            Permission(code=permission.value, name=permission.value)
            for permission in permissions
        ],
    )
    user = User(
        user_id=7,
        username="test-user",
        username_normalized="test-user",
        display_name="Тестовый пользователь",
        password_hash="hash",
        must_change_password=must_change_password,
        roles=[role],
    )
    now = datetime.now(UTC)
    return UserSession(
        session_id=3,
        user_id=user.user_id,
        token_hash=b"a" * 32,
        csrf_token_hash=b"b" * 32,
        created_at=now,
        last_seen_at=now,
        absolute_expires_at=now + timedelta(hours=12),
        user=user,
    )


def _protected_app(session_service: AsyncMock) -> FastAPI:
    test_app = FastAPI()
    queue_read_dependency = require_permission(PermissionCode.QUEUE_READ)
    QueueReadDep = Annotated[AuthContext, Depends(queue_read_dependency)]

    @test_app.get("/protected")
    async def protected(auth: QueueReadDep) -> dict[str, int]:
        return {"user_id": auth.user.user_id}

    test_app.dependency_overrides[get_user_session_service] = lambda: session_service
    return test_app


def test_permission_dependency_allows_user_with_permission() -> None:
    session_service = AsyncMock()
    session_service.validate.return_value = _user_session(
        permissions={PermissionCode.QUEUE_READ},
    )
    test_app = _protected_app(session_service)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={"__Host-rp_session": SESSION_TOKEN},
        ) as client:
            response = await client.get("/protected")

        assert response.status_code == 200
        assert response.json() == {"user_id": 7}

    asyncio.run(scenario())
    session_service.validate.assert_awaited_once_with(SESSION_TOKEN)


def test_permission_dependency_rejects_missing_session() -> None:
    session_service = AsyncMock()
    test_app = _protected_app(session_service)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
        ) as client:
            response = await client.get("/protected")

        assert response.status_code == 401
        assert response.json() == {"detail": "Требуется вход"}
        assert response.headers["www-authenticate"] == "Session"

    asyncio.run(scenario())
    session_service.validate.assert_not_awaited()


def test_permission_dependency_rejects_invalid_or_blocked_user_session() -> None:
    session_service = AsyncMock()
    session_service.validate.side_effect = InvalidSessionError()
    test_app = _protected_app(session_service)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={"__Host-rp_session": SESSION_TOKEN},
        ) as client:
            response = await client.get("/protected")

        assert response.status_code == 401
        assert response.json() == {"detail": "Требуется вход"}

    asyncio.run(scenario())


def test_permission_dependency_rejects_user_without_permission() -> None:
    session_service = AsyncMock()
    session_service.validate.return_value = _user_session(
        permissions={PermissionCode.SOURCES_READ},
    )
    test_app = _protected_app(session_service)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={"__Host-rp_session": SESSION_TOKEN},
        ) as client:
            response = await client.get("/protected")

        assert response.status_code == 403
        assert response.json() == {"detail": "Недостаточно прав"}

    asyncio.run(scenario())


def test_permission_dependency_blocks_business_api_until_password_changed() -> None:
    session_service = AsyncMock()
    session_service.validate.return_value = _user_session(
        permissions={PermissionCode.QUEUE_READ},
        must_change_password=True,
    )
    test_app = _protected_app(session_service)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={"__Host-rp_session": SESSION_TOKEN},
        ) as client:
            response = await client.get("/protected")

        assert response.status_code == 403
        assert response.json() == {"detail": "Требуется сменить временный пароль"}

    asyncio.run(scenario())
