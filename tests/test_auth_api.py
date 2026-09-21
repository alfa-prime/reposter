from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from news_reposter.api.dependencies import (
    get_authentication_service,
    get_user_session_service,
)
from news_reposter.auth.session_tokens import SessionTokens, hash_token
from news_reposter.db.models import Permission, Role, User, UserSession
from news_reposter.main import app
from news_reposter.services.authentication import (
    AuthenticationResult,
    InvalidCredentialsError,
    LoginRateLimitedError,
)
from news_reposter.services.user_sessions import CreatedSession, InvalidSessionError

SESSION_TOKEN = "session-secret"
CSRF_TOKEN = "csrf-secret"


def _auth_data() -> tuple[AuthenticationResult, UserSession]:
    permission = Permission(code="queue.read", name="Просмотр очереди")
    role = Role(
        code="viewer",
        name="Наблюдатель",
        is_active=True,
        permissions=[permission],
    )
    user = User(
        user_id=1,
        username="admin",
        username_normalized="admin",
        display_name="Администратор",
        password_hash="hash",
        must_change_password=False,
        roles=[role],
    )
    now = datetime.now(UTC)
    user_session = UserSession(
        session_id=11,
        user_id=user.user_id,
        token_hash=hash_token(SESSION_TOKEN),
        csrf_token_hash=hash_token(CSRF_TOKEN),
        created_at=now,
        last_seen_at=now,
        absolute_expires_at=now + timedelta(hours=12),
        user=user,
    )
    created = CreatedSession(
        session=user_session,
        tokens=SessionTokens(
            session_token=SESSION_TOKEN,
            csrf_token=CSRF_TOKEN,
        ),
    )
    return AuthenticationResult(user=user, created_session=created), user_session


@pytest.fixture
def auth_services() -> tuple[AsyncMock, AsyncMock]:
    result, user_session = _auth_data()
    authentication = AsyncMock()
    authentication.authenticate.return_value = result
    sessions = AsyncMock()
    sessions.validate.return_value = user_session
    sessions.revoke.return_value = True
    sessions.revoke_all_for_user.return_value = 1

    app.dependency_overrides[get_authentication_service] = lambda: authentication
    app.dependency_overrides[get_user_session_service] = lambda: sessions
    yield authentication, sessions
    app.dependency_overrides.pop(get_authentication_service, None)
    app.dependency_overrides.pop(get_user_session_service, None)


def test_login_me_and_logout_use_secure_cookies(
    auth_services: tuple[AsyncMock, AsyncMock],
) -> None:
    authentication, sessions = auth_services

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
        ) as client:
            logged_in = await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "correct-password"},
                headers={"Origin": "https://test"},
            )
            assert logged_in.status_code == 200
            assert logged_in.headers["cache-control"] == "no-store"
            assert logged_in.json() == {
                "user_id": 1,
                "username": "admin",
                "display_name": "Администратор",
                "avatar_url": None,
                "must_change_password": False,
                "roles": [{"code": "viewer", "name": "Наблюдатель"}],
                "permissions": ["queue.read"],
            }
            assert SESSION_TOKEN not in logged_in.text
            assert CSRF_TOKEN not in logged_in.text

            cookies = logged_in.headers.get_list("set-cookie")
            session_cookie = next(
                value for value in cookies if value.startswith("__Host-rp_session=")
            )
            csrf_cookie = next(
                value for value in cookies if value.startswith("__Host-rp_csrf=")
            )
            assert "HttpOnly" in session_cookie
            assert "HttpOnly" not in csrf_cookie
            for cookie in cookies:
                assert "Secure" in cookie
                assert "SameSite=strict" in cookie
                assert "Path=/" in cookie
                assert "Domain=" not in cookie

            current = await client.get("/api/v1/auth/me")
            assert current.status_code == 200
            assert current.headers["cache-control"] == "no-store"
            assert current.json() == logged_in.json()

            rejected = await client.post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": "wrong"},
            )
            assert rejected.status_code == 403
            sessions.revoke.assert_not_awaited()

            logged_out = await client.post(
                "/api/v1/auth/logout",
                headers={
                    "Origin": "https://test",
                    "X-CSRF-Token": CSRF_TOKEN,
                },
            )
            assert logged_out.status_code == 204
            assert logged_out.headers["cache-control"] == "no-store"
            assert logged_out.content == b""
            deleted = logged_out.headers.get_list("set-cookie")
            assert len(deleted) == 2
            assert all("Max-Age=0" in cookie for cookie in deleted)

    asyncio.run(scenario())
    authentication.authenticate.assert_awaited_once()
    sessions.revoke.assert_awaited_once()


def test_logout_all_revokes_every_session(
    auth_services: tuple[AsyncMock, AsyncMock],
) -> None:
    _, sessions = auth_services

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={
                "__Host-rp_session": SESSION_TOKEN,
                "__Host-rp_csrf": CSRF_TOKEN,
            },
        ) as client:
            response = await client.post(
                "/api/v1/auth/logout-all",
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )
            assert response.status_code == 204

    asyncio.run(scenario())
    sessions.revoke_all_for_user.assert_awaited_once_with(
        1,
        reason="logout_all",
    )


def test_login_has_generic_errors_and_rate_limit_headers(
    auth_services: tuple[AsyncMock, AsyncMock],
) -> None:
    authentication, _ = auth_services

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
        ) as client:
            authentication.authenticate.side_effect = InvalidCredentialsError()
            invalid = await client.post(
                "/api/v1/auth/login",
                json={"username": "missing", "password": "wrong"},
            )
            assert invalid.status_code == 401
            assert invalid.json() == {"detail": "Неверный логин или пароль"}
            assert invalid.headers["www-authenticate"] == "Session"

            authentication.authenticate.side_effect = LoginRateLimitedError(37)
            limited = await client.post(
                "/api/v1/auth/login",
                json={"username": "missing", "password": "wrong"},
            )
            assert limited.status_code == 429
            assert limited.headers["retry-after"] == "37"

    asyncio.run(scenario())


def test_session_and_origin_fail_closed(
    auth_services: tuple[AsyncMock, AsyncMock],
) -> None:
    authentication, sessions = auth_services

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
        ) as client:
            missing = await client.get("/api/v1/auth/me")
            assert missing.status_code == 401
            assert missing.headers["www-authenticate"] == "Session"

            sessions.validate.side_effect = InvalidSessionError()
            client.cookies.set("__Host-rp_session", "invalid")
            invalid = await client.get("/api/v1/auth/me")
            assert invalid.status_code == 401

            cross_site = await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "password"},
                headers={"Origin": "https://attacker.example"},
            )
            assert cross_site.status_code == 403

    asyncio.run(scenario())
    authentication.authenticate.assert_not_awaited()
