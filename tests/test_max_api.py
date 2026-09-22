import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx

import news_reposter.api.v1.max as max_api
from news_reposter.api.dependencies import get_current_auth, get_http_client
from news_reposter.auth.rbac import PermissionCode
from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import get_settings
from news_reposter.main import app

CSRF_TOKEN = "max-api-csrf-token"
CSRF_COOKIE_NAME = get_settings().auth_csrf_cookie_name


def auth_context(*permissions: PermissionCode) -> SimpleNamespace:
    return SimpleNamespace(
        user=SimpleNamespace(must_change_password=False),
        session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
        permission_codes=frozenset(permission.value for permission in permissions),
    )


def test_max_helpers_require_manage_permission_and_csrf(monkeypatch) -> None:
    max_client = SimpleNamespace(
        get_subscriptions=AsyncMock(return_value={"subscriptions": []}),
        create_subscription=AsyncMock(return_value={"success": True}),
    )
    monkeypatch.setattr(
        max_api,
        "max_client_from_settings",
        lambda _http_client: max_client,
    )
    monkeypatch.setattr(
        max_api,
        "get_settings",
        lambda: SimpleNamespace(
            max_webhook_url="https://example.test/api/v1/max/webhook",
            max_webhook_secret="valid-secret",
        ),
    )
    app.dependency_overrides[get_http_client] = lambda: Mock(spec=httpx.AsyncClient)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
        ) as client:
            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.TARGETS_MANAGE
            )
            subscriptions = await client.get("/api/v1/max/subscriptions")
            created = await client.post(
                "/api/v1/max/subscriptions/channel-discovery",
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )
            missing_csrf = await client.post(
                "/api/v1/max/subscriptions/channel-discovery"
            )
            foreign_origin = await client.post(
                "/api/v1/max/subscriptions/channel-discovery",
                headers={
                    "X-CSRF-Token": CSRF_TOKEN,
                    "Origin": "https://evil.example",
                },
            )

            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.TARGETS_READ
            )
            forbidden = await client.get("/api/v1/max/subscriptions")

        assert subscriptions.status_code == 200
        assert subscriptions.json() == {"subscriptions": []}
        assert created.status_code == 200
        assert created.json() == {"success": True}
        assert missing_csrf.status_code == 403
        assert missing_csrf.json() == {"detail": "Недействительный CSRF-токен"}
        assert foreign_origin.status_code == 403
        assert foreign_origin.json() == {"detail": "Недопустимый источник запроса"}
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": "Недостаточно прав"}

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_auth, None)
        app.dependency_overrides.pop(get_http_client, None)
