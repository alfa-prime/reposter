import asyncio
import ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status

import news_reposter.api.dependencies as dependencies
import news_reposter.main as main_module
from news_reposter.api.dependencies import get_http_client, get_llm_provider
from news_reposter.config import Settings
from news_reposter.http_client import create_http_client, create_http_ssl_context


def test_http_ssl_context_adds_custom_ca_to_system_trust(monkeypatch) -> None:
    context = Mock(spec=ssl.SSLContext)
    create_default_context = Mock(return_value=context)
    monkeypatch.setattr(ssl, "create_default_context", create_default_context)

    result = create_http_ssl_context("/app/certs/russian_trusted_ca.pem")

    assert result is context
    create_default_context.assert_called_once_with()
    context.load_verify_locations.assert_called_once_with(
        cafile="/app/certs/russian_trusted_ca.pem"
    )


def test_http_ssl_context_reports_missing_ca_file(tmp_path) -> None:
    missing_path = tmp_path / "missing.pem"

    with pytest.raises(RuntimeError, match="Не удалось загрузить HTTP_CA_FILE"):
        create_http_ssl_context(str(missing_path))


def test_create_http_client_uses_shared_pool_settings() -> None:
    settings = Settings(
        http_timeout_seconds=45,
        http_connect_timeout_seconds=7,
        http_max_connections=80,
        http_max_keepalive_connections=30,
        http_keepalive_expiry_seconds=25,
        http_trust_env=False,
    )

    client = create_http_client(settings)
    try:
        assert client.timeout.read == 45
        assert client.timeout.write == 45
        assert client.timeout.pool == 45
        assert client.timeout.connect == 7
        assert client.follow_redirects is True
        assert client.headers["User-Agent"] == "news-reposter/0.1.0"

        pool = client._transport._pool  # noqa: SLF001
        assert pool._max_connections == 80  # noqa: SLF001
        assert pool._max_keepalive_connections == 30  # noqa: SLF001
        assert pool._keepalive_expiry == 25  # noqa: SLF001
    finally:
        asyncio.run(client.aclose())


def test_http_client_dependency_returns_app_state_client() -> None:
    client = Mock(spec=httpx.AsyncClient)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(http_client=client))
    )

    assert get_http_client(request) is client


def test_llm_provider_dependency_reuses_app_state_provider(monkeypatch) -> None:
    http_client = Mock(spec=httpx.AsyncClient)
    provider = SimpleNamespace(name="gigachat")
    factory = Mock(return_value=provider)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(http_client=http_client, llm_provider=None)
        )
    )
    monkeypatch.setattr(dependencies, "build_llm_provider", factory)

    assert get_llm_provider(request) is provider
    assert get_llm_provider(request) is provider
    factory.assert_called_once_with(http_client)


def test_llm_provider_dependency_reports_missing_configuration(monkeypatch) -> None:
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                http_client=Mock(spec=httpx.AsyncClient),
                llm_provider=None,
            )
        )
    )
    monkeypatch.setattr(
        dependencies,
        "build_llm_provider",
        Mock(side_effect=RuntimeError("Для GigaChat не задан GIGACHAT_CREDENTIALS")),
    )

    with pytest.raises(HTTPException) as error:
        get_llm_provider(request)

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "GIGACHAT_CREDENTIALS" in error.value.detail


def test_lifespan_registers_and_closes_http_client(monkeypatch) -> None:
    client = AsyncMock(spec=httpx.AsyncClient)
    collection_scheduler = SimpleNamespace(start=Mock(), stop=AsyncMock())
    publication_scheduler = SimpleNamespace(start=Mock(), stop=AsyncMock())
    collection_scheduler_factory = Mock(return_value=collection_scheduler)
    publication_scheduler_factory = Mock(return_value=publication_scheduler)
    close_database = AsyncMock()

    monkeypatch.setattr(main_module, "create_http_client", lambda: client)
    monkeypatch.setattr(
        main_module,
        "CollectionScheduler",
        collection_scheduler_factory,
    )
    monkeypatch.setattr(
        main_module,
        "PublicationScheduler",
        publication_scheduler_factory,
    )
    monkeypatch.setattr(main_module, "close_database", close_database)

    async def scenario() -> None:
        app = FastAPI()
        async with main_module.lifespan(app):
            assert app.state.http_client is client
            assert app.state.llm_provider is None
            assert app.state.collection_scheduler is collection_scheduler
            collection_scheduler_factory.assert_called_once_with(client)
            publication_scheduler_factory.assert_called_once_with(client)
            collection_scheduler.start.assert_called_once_with()
            publication_scheduler.start.assert_called_once_with()
            client.aclose.assert_not_awaited()

        publication_scheduler.stop.assert_awaited_once_with()
        collection_scheduler.stop.assert_awaited_once_with()
        client.aclose.assert_awaited_once_with()
        close_database.assert_awaited_once_with()

    asyncio.run(scenario())
