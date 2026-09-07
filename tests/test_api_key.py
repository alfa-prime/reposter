import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

import news_reposter.api.dependencies as dependencies


def set_expected_api_key(
    monkeypatch: pytest.MonkeyPatch,
    api_key: str | None,
) -> None:
    """Подменяет настройку API-ключа в тесте."""

    def settings() -> SimpleNamespace:
        """Возвращает минимальный набор тестовых настроек."""

        return SimpleNamespace(api_key=api_key)

    monkeypatch.setattr(dependencies, "get_settings", settings)


def test_valid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет разрешение запроса с правильным ключом."""

    set_expected_api_key(monkeypatch, "correct-secret-key")

    assert asyncio.run(dependencies.require_api_key("correct-secret-key")) is None


def test_invalid_api_key_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет отказ для отсутствующего и неверного ключа."""

    set_expected_api_key(monkeypatch, "correct-secret-key")

    for provided_api_key in (None, "wrong-key"):
        with pytest.raises(HTTPException) as error:
            asyncio.run(dependencies.require_api_key(provided_api_key))

        assert error.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.value.detail == "Неверный или отсутствующий API-ключ"


def test_missing_api_key_setting_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет закрытый доступ при отсутствии ключа в настройках."""

    set_expected_api_key(monkeypatch, None)

    with pytest.raises(HTTPException) as error:
        asyncio.run(dependencies.require_api_key("any-key"))

    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert error.value.detail == "API_KEY не настроен"
