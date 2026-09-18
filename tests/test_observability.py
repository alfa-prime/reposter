import asyncio
import logging
import re

import httpx
from fastapi import FastAPI

from news_reposter.logging_config import RequestIdFilter, request_id_context
from news_reposter.observability import (
    REQUEST_ID_HEADER,
    request_id_middleware,
    unexpected_exception_handler,
)


def make_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(Exception, unexpected_exception_handler)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"request_id": request_id_context.get()}

    @app.get("/failed")
    async def failed() -> None:
        raise RuntimeError("Внутренняя диагностическая информация")

    return app


def test_request_id_is_propagated_to_context_and_response() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=make_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/ok",
                headers={REQUEST_ID_HEADER: "frontend-request-42"},
            )

        assert response.status_code == 200
        assert response.headers[REQUEST_ID_HEADER] == "frontend-request-42"
        assert response.json() == {"request_id": "frontend-request-42"}

    asyncio.run(scenario())


def test_invalid_request_id_is_replaced() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=make_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/ok",
                headers={REQUEST_ID_HEADER: "invalid value with spaces"},
            )

        generated = response.headers[REQUEST_ID_HEADER]
        assert re.fullmatch(r"[0-9a-f]{32}", generated)
        assert response.json() == {"request_id": generated}

    asyncio.run(scenario())


def test_unexpected_error_returns_safe_response_with_request_id() -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=make_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/failed",
                headers={REQUEST_ID_HEADER: "failed-request-7"},
            )

        assert response.status_code == 500
        assert response.headers[REQUEST_ID_HEADER] == "failed-request-7"
        assert response.json() == {
            "detail": "Внутренняя ошибка сервера",
            "request_id": "failed-request-7",
        }
        assert "диагностическая" not in response.text.lower()

    asyncio.run(scenario())


def test_request_id_filter_uses_context_value() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=(),
        exc_info=None,
    )
    token = request_id_context.set("request-from-context")
    try:
        assert RequestIdFilter().filter(record) is True
    finally:
        request_id_context.reset(token)

    assert record.request_id == "request-from-context"
