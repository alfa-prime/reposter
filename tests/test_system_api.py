import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.v1.system import database_health, health


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
