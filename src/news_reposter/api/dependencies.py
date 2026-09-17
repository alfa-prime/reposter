from secrets import compare_digest
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from news_reposter.config import get_settings
from news_reposter.llm import LLMProvider
from news_reposter.llm.factory import build_llm_provider

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="APIKeyHeader",
    description="API-ключ сервиса из переменной окружения `API_KEY`.",
    auto_error=False,
)

API_KEY_RESPONSES = {
    401: {"description": "Неверный или отсутствующий API-ключ"},
    503: {"description": "API-ключ не настроен на сервере"},
}


async def require_api_key(
    provided_api_key: Annotated[str | None, Security(api_key_header)],
) -> None:
    """Проверяет API-ключ из заголовка запроса."""

    expected_api_key = get_settings().api_key
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_KEY не настроен",
        )

    if provided_api_key is None or not compare_digest(
        provided_api_key,
        expected_api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или отсутствующий API-ключ",
            headers={"WWW-Authenticate": "ApiKey"},
        )


ApiKeyDep = Annotated[None, Depends(require_api_key)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Возвращает общий HTTP-клиент текущего процесса FastAPI."""

    return request.app.state.http_client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def get_llm_provider(request: Request) -> LLMProvider:
    """Лениво создаёт один LLM-провайдер на процесс приложения."""

    provider: LLMProvider | None = getattr(request.app.state, "llm_provider", None)
    if provider is not None:
        return provider

    try:
        provider = build_llm_provider(get_http_client(request))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    request.app.state.llm_provider = provider
    return provider


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
