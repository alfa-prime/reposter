import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
from fastapi import FastAPI

import news_reposter.main as main_module
from news_reposter.api.dependencies import get_http_client
from news_reposter.config import Settings
from news_reposter.http_client import create_http_client


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
            assert app.state.collection_scheduler is collection_scheduler
            collection_scheduler_factory.assert_called_once_with(client)
            publication_scheduler_factory.assert_called_once_with()
            collection_scheduler.start.assert_called_once_with()
            publication_scheduler.start.assert_called_once_with()
            client.aclose.assert_not_awaited()

        publication_scheduler.stop.assert_awaited_once_with()
        collection_scheduler.stop.assert_awaited_once_with()
        client.aclose.assert_awaited_once_with()
        close_database.assert_awaited_once_with()

    asyncio.run(scenario())
