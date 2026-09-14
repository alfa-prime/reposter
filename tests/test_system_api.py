import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

import news_reposter.api.v1.system as system_api
from news_reposter.api.v1.system import collect_now, database_health, health, llm_test
from news_reposter.llm import LLMProviderError, RewriteResult


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

    async def fake_collect() -> dict[str, int]:
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

    response = asyncio.run(collect_now(None))

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
        asyncio.run(collect_now(None))

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


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
    monkeypatch.setattr(system_api, "build_llm_provider", lambda: provider)

    response = asyncio.run(llm_test(None))

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


def test_llm_test_returns_503_when_provider_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверка LLM сообщает об отсутствующей конфигурации отдельно от сетевой ошибки."""

    def fail_build() -> None:
        raise RuntimeError("Для GigaChat не задан GIGACHAT_CREDENTIALS")

    monkeypatch.setattr(system_api, "build_llm_provider", fail_build)

    with pytest.raises(HTTPException) as error:
        asyncio.run(llm_test(None))

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "GIGACHAT_CREDENTIALS" in error.value.detail


def test_llm_test_returns_502_when_provider_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ошибка внешнего LLM отделяется от ошибки конфигурации приложения."""

    provider = SimpleNamespace(
        rewrite=AsyncMock(side_effect=LLMProviderError("GigaChat не выполнил запрос (401)"))
    )
    monkeypatch.setattr(system_api, "build_llm_provider", lambda: provider)

    with pytest.raises(HTTPException) as error:
        asyncio.run(llm_test(None))

    assert error.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert error.value.detail == "GigaChat не выполнил запрос (401)"
