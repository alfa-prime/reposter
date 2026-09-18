import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from news_reposter.logging_config import request_id_context

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def request_id_from_header(value: str | None) -> str:
    """Принимает безопасный внешний ID или создаёт новый."""

    if value and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid4().hex


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Связывает HTTP-ответ и прикладные логи единым request_id."""

    request_id = request_id_from_header(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    try:
        try:
            response = await call_next(request)
        except Exception as exc:
            response = await unexpected_exception_handler(request, exc)
        response.headers[REQUEST_ID_HEADER] = request_id
        if (
            request.url.path != "/health"
            and response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
        ):
            logger.info(
                "action=http_request method=%s path=%s status_code=%s duration_ms=%s client_ip=%s",
                request.method,
                request.url.path,
                response.status_code,
                round((time.perf_counter() - started_at) * 1000),
                request.client.host if request.client else "-",
            )
        return response
    finally:
        request_id_context.reset(token)


async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Логирует неожиданный сбой и возвращает безопасный ответ 500."""

    request_id = getattr(request.state, "request_id", uuid4().hex)
    token = request_id_context.set(request_id)
    try:
        logger.error(
            "action=http_request status=failed method=%s path=%s error_type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    finally:
        request_id_context.reset(token)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Внутренняя ошибка сервера",
            "request_id": request_id,
        },
        headers={REQUEST_ID_HEADER: request_id},
    )
