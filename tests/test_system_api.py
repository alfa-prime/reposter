import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

import news_reposter.api.v1.system as system_api
from news_reposter.api.dependencies import (
    get_current_auth,
    get_http_client,
    get_llm_provider,
)
from news_reposter.api.v1.system import collect_now, database_health, health, llm_test
from news_reposter.auth.rbac import PermissionCode
from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import get_settings
from news_reposter.llm import LLMProviderError, RewriteResult
from news_reposter.main import app

CSRF_TOKEN = "collect-now-csrf-token"
CSRF_COOKIE_NAME = get_settings().auth_csrf_cookie_name


def test_health() -> None:
    """Проверяет простой ответ о состоянии приложения."""

    assert asyncio.run(health()) == {"status": "ok"}


def test_database_health() -> None:
    """Проверяет успешный асинхронный запрос к PostgreSQL."""

    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one.return_value = 1
    session.execute.return_value = result

    response = asyncio.run(database_health(session))

    assert response == {"status": "ok", "database": "connected"}
    statement = session.execute.await_args.args[0]
    assert str(statement) == "SELECT 1"


def test_database_health_returns_503_when_database_is_unavailable() -> None:
    """Проверяет ответ 503 при ошибке подключения к PostgreSQL."""

    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = OperationalError(
        statement="SELECT 1",
        params=None,
        orig=OSError("connection refused"),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(database_health(session))

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert error.value.detail == "PostgreSQL недоступен"


def test_collect_now_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ручной запуск возвращает понятную сводку для админки."""

    http_client = Mock(spec=httpx.AsyncClient)

    async def fake_collect(client: object, _trigger: object) -> dict[str, int]:
        assert client is http_client
        return {
            "sources_checked": 2,
            "posts_created": 3,
            "queue_items_created": 5,
            "errors": 0,
        }

    monkeypatch.setattr(
        system_api,
        "get_settings",
        lambda: SimpleNamespace(vk_access_token="secret"),
    )
    monkeypatch.setattr(system_api, "collect_active_sources_once", fake_collect)

    response = asyncio.run(collect_now(None, None, None, http_client))

    assert response == {
        "status": "ok",
        "sources_checked": 2,
        "posts_created": 3,
        "queue_items_created": 5,
        "errors": 0,
    }


def test_collect_now_requires_vk_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ручной сбор явно сообщает, если VK не настроен."""

    monkeypatch.setattr(
        system_api,
        "get_settings",
        lambda: SimpleNamespace(vk_access_token=None),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(collect_now(None, None, None, Mock(spec=httpx.AsyncClient)))

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_collect_now_requires_permission_csrf_and_same_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_client = Mock(spec=httpx.AsyncClient)

    async def fake_collect(_client: object, _trigger: object) -> dict[str, int]:
        return {
            "sources_checked": 1,
            "posts_created": 0,
            "queue_items_created": 0,
            "errors": 0,
        }

    monkeypatch.setattr(
        system_api,
        "get_settings",
        lambda: SimpleNamespace(vk_access_token="secret"),
    )
    monkeypatch.setattr(system_api, "collect_active_sources_once", fake_collect)
    app.dependency_overrides[get_http_client] = lambda: http_client

    def auth_context(*permissions: PermissionCode) -> SimpleNamespace:
        return SimpleNamespace(
            user=SimpleNamespace(must_change_password=False),
            session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
            permission_codes=frozenset(permission.value for permission in permissions),
        )

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
        ) as client:
            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.COLLECTION_RUN
            )
            allowed = await client.post(
                "/api/v1/system/collect-now",
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )
            missing_csrf = await client.post("/api/v1/system/collect-now")
            foreign_origin = await client.post(
                "/api/v1/system/collect-now",
                headers={
                    "X-CSRF-Token": CSRF_TOKEN,
                    "Origin": "https://evil.example",
                },
            )

            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.SCHEDULER_READ
            )
            forbidden = await client.post(
                "/api/v1/system/collect-now",
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )

        assert allowed.status_code == 200
        assert allowed.json()["sources_checked"] == 1
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


def test_llm_test_returns_provider_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка LLM возвращает только безопасные данные о реальном ответе провайдера."""

    provider = SimpleNamespace(
        rewrite=AsyncMock(
            return_value=RewriteResult(
                text="Сегодня в Мурманске хорошая погода.",
                provider="gigachat",
                model="GigaChat-2-Pro",
                usage={"total_tokens": 17},
            )
        )
    )
    response = asyncio.run(llm_test(None, None, None, provider))

    assert response == {
        "status": "ok",
        "provider": "gigachat",
        "model": "GigaChat-2-Pro",
        "text": "Сегодня в Мурманске хорошая погода.",
        "usage": {"total_tokens": 17},
    }
    request = provider.rewrite.await_args.args[0]
    assert request.text == "В Мурманске сегодня хорошая погода."
    assert request.max_tokens == 128


def test_llm_test_returns_502_when_provider_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ошибка внешнего LLM отделяется от ошибки конфигурации приложения."""

    provider = SimpleNamespace(
        rewrite=AsyncMock(
            side_effect=LLMProviderError("GigaChat не выполнил запрос (401)")
        )
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(llm_test(None, None, None, provider))

    assert error.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert error.value.detail == "GigaChat не выполнил запрос (401)"


def test_llm_test_requires_rewrite_permission_csrf_and_same_origin() -> None:
    provider = SimpleNamespace(
        rewrite=AsyncMock(
            return_value=RewriteResult(
                text="Тест выполнен.",
                provider="gigachat",
                model="GigaChat-2-Pro",
                usage={"total_tokens": 5},
            )
        )
    )
    app.dependency_overrides[get_llm_provider] = lambda: provider

    def auth_context(*permissions: PermissionCode) -> SimpleNamespace:
        return SimpleNamespace(
            user=SimpleNamespace(must_change_password=False),
            session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
            permission_codes=frozenset(permission.value for permission in permissions),
        )

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
        ) as client:
            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.QUEUE_REWRITE
            )
            allowed = await client.post(
                "/api/v1/system/llm-test",
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )
            missing_csrf = await client.post("/api/v1/system/llm-test")
            foreign_origin = await client.post(
                "/api/v1/system/llm-test",
                headers={
                    "X-CSRF-Token": CSRF_TOKEN,
                    "Origin": "https://evil.example",
                },
            )

            app.dependency_overrides[get_current_auth] = lambda: auth_context(
                PermissionCode.QUEUE_READ
            )
            forbidden = await client.post(
                "/api/v1/system/llm-test",
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )

        assert allowed.status_code == 200
        assert allowed.json()["provider"] == "gigachat"
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
        app.dependency_overrides.pop(get_llm_provider, None)
