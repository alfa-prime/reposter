import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from news_reposter.api.dependencies import get_current_auth
from news_reposter.api.journal_pagination import (
    cursor_context,
    decode_cursor,
    encode_cursor,
    validate_pagination,
)
from news_reposter.api.journal_session import get_journal_session
from news_reposter.config import get_settings
from news_reposter.main import app


def test_cursor_round_trip_and_filter_binding() -> None:
    context = cursor_context("editorial", {"target": 9})
    timestamp = datetime(2026, 9, 27, 18, 30, 1, 123456, tzinfo=UTC)
    value = encode_cursor(context, 42, timestamp)
    decoded = decode_cursor(value, context, audit=True)
    assert decoded.row_id == 42
    assert decoded.created_at == timestamp
    with pytest.raises(HTTPException) as error:
        decode_cursor(value, cursor_context("editorial", {"target": 10}), audit=True)
    assert error.value.status_code == 422
    with pytest.raises(HTTPException):
        decode_cursor(value, context)


@pytest.mark.parametrize("value", ["", "!", "x" * 513, "e30", "bm90LWpzb24"])
def test_malformed_cursor_is_a_validation_error(value: str) -> None:
    with pytest.raises(HTTPException) as error:
        decode_cursor(value, "context")
    assert error.value.status_code == 422


def test_pagination_modes_cannot_be_mixed() -> None:
    validate_pagination("cursor", None, 0)
    validate_pagination("offset", None, 100)
    for mode, cursor, offset in [("cursor", None, 1), ("offset", "cursor", 0)]:
        with pytest.raises(HTTPException):
            validate_pagination(mode, cursor, offset)


def test_unauthorized_journal_request_does_not_acquire_a_database_connection() -> None:
    async def forbidden_session():
        pytest.fail("journal DB must not be acquired before permission checks")
        yield

    app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
        user=SimpleNamespace(must_change_password=False), permission_codes=frozenset()
    )
    app.dependency_overrides[get_journal_session] = forbidden_session

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client:
            for path in [
                "/api/v1/admin/audit",
                "/api/v1/admin/audit/editorial",
                "/api/v1/system/collection/runs",
            ]:
                response = await client.get(path)
                assert response.status_code == 403

    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.clear()


def test_journal_client_timeout_rolls_back_and_returns_503() -> None:
    async def scenario() -> None:
        session = SimpleNamespace(execute=AsyncMock(), rollback=AsyncMock())
        dependency = get_journal_session(session)
        await anext(dependency)
        with pytest.raises(HTTPException) as error:
            await dependency.athrow(TimeoutError())
        assert error.value.status_code == 503
        session.rollback.assert_awaited_once()
        assert (
            session.execute.call_args.args[1]["timeout"]
            == f"{int(get_settings().database_journal_timeout_seconds * 1000)}ms"
        )

    asyncio.run(scenario())
