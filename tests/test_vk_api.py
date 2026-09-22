import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import httpx

import news_reposter.api.v1.vk as vk_api
from news_reposter.api.dependencies import get_current_auth, get_http_client
from news_reposter.auth.rbac import PermissionCode
from news_reposter.integrations.vk import VKPost
from news_reposter.main import app


def auth_context(*permissions: PermissionCode) -> SimpleNamespace:
    return SimpleNamespace(
        user=SimpleNamespace(must_change_password=False),
        permission_codes=frozenset(permission.value for permission in permissions),
    )


def test_vk_helpers_require_source_permissions(monkeypatch) -> None:
    class FakeVKClient:
        async def get_group_info(self, _link: str) -> dict[str, str]:
            return {
                "name": "Новости Мурманска",
                "screen_name": "murmansk_news",
                "photo_100": "https://example.test/icon.jpg",
            }

        async def get_latest_post(self, _group: str) -> VKPost:
            return VKPost(id=10, owner_id=-20, date=1_700_000_000, text="Новость")

    monkeypatch.setattr(vk_api, "_client", lambda _http_client: FakeVKClient())
    app.dependency_overrides[get_http_client] = lambda: Mock(spec=httpx.AsyncClient)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://test"
        ) as client:
            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.SOURCES_MANAGE,
                PermissionCode.SOURCES_READ,
            )
            source_info = await client.get(
                "/api/v1/vk/source-info",
                params={"link": "https://vk.ru/murmansk_news"},
            )
            latest = await client.get(
                "/api/v1/vk/posts/latest",
                params={"group": "murmansk_news"},
            )

            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.SOURCES_READ
            )
            source_info_forbidden = await client.get(
                "/api/v1/vk/source-info",
                params={"link": "https://vk.ru/murmansk_news"},
            )

            app.dependency_overrides.pop(get_current_auth, None)
            unauthorized = await client.get(
                "/api/v1/vk/posts/latest",
                params={"group": "murmansk_news"},
            )

        assert source_info.status_code == 200
        assert source_info.json()["name"] == "Новости Мурманска"
        assert latest.status_code == 200
        assert latest.json()["id"] == 10
        assert source_info_forbidden.status_code == 403
        assert source_info_forbidden.json() == {"detail": "Недостаточно прав"}
        assert unauthorized.status_code == 401
        assert unauthorized.json() == {"detail": "Требуется вход"}

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_current_auth, None)
        app.dependency_overrides.pop(get_http_client, None)
