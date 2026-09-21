from secrets import compare_digest
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.context import AuthContext
from news_reposter.auth.session_tokens import token_matches
from news_reposter.config import get_settings
from news_reposter.db.session import get_db_session
from news_reposter.llm import LLMProvider
from news_reposter.llm.factory import build_llm_provider
from news_reposter.services.authentication import AuthenticationService
from news_reposter.services.user_sessions import (
    InvalidSessionError,
    UserSessionService,
)

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

SESSION_AUTH_RESPONSES = {
    401: {"description": "Требуется действующая пользовательская сессия"},
}

CSRF_AUTH_RESPONSES = {
    **SESSION_AUTH_RESPONSES,
    403: {"description": "Недействительный CSRF-токен или источник запроса"},
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

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_authentication_service(session: DbSessionDep) -> AuthenticationService:
    """Создаёт сервис входа в рамках транзакции текущего запроса."""

    return AuthenticationService(session)


AuthenticationServiceDep = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


def get_user_session_service(session: DbSessionDep) -> UserSessionService:
    """Создаёт сервис пользовательских сессий для текущего запроса."""

    return UserSessionService(session)


UserSessionServiceDep = Annotated[
    UserSessionService,
    Depends(get_user_session_service),
]

settings = get_settings()
session_cookie = APIKeyCookie(
    name=settings.auth_session_cookie_name,
    scheme_name="SessionCookie",
    description="Непрозрачный токен серверной пользовательской сессии.",
    auto_error=False,
)


async def get_current_auth(
    provided_session_token: Annotated[str | None, Security(session_cookie)],
    session_service: UserSessionServiceDep,
) -> AuthContext:
    """Проверяет cookie и возвращает пользователя с актуальными правами."""

    if provided_session_token is None:
        raise _unauthorized_session()
    try:
        user_session = await session_service.validate(provided_session_token)
    except InvalidSessionError as exc:
        raise _unauthorized_session() from exc
    return AuthContext.from_session(user_session)


AuthContextDep = Annotated[AuthContext, Depends(get_current_auth)]


async def require_csrf(
    request: Request,
    auth: AuthContextDep,
    provided_csrf_token: Annotated[
        str | None,
        Header(alias="X-CSRF-Token"),
    ] = None,
) -> AuthContext:
    """Проверяет двойной CSRF-токен для изменяющего запроса."""

    csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name)
    if (
        provided_csrf_token is None
        or csrf_cookie is None
        or not compare_digest(provided_csrf_token, csrf_cookie)
        or not token_matches(
            provided_csrf_token,
            auth.session.csrf_token_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недействительный CSRF-токен",
        )
    return auth


CsrfAuthContextDep = Annotated[AuthContext, Depends(require_csrf)]


async def require_same_origin(request: Request) -> None:
    """Отклоняет браузерный изменяющий запрос с другого источника."""

    origin = request.headers.get("Origin")
    if origin is None:
        return

    parsed = urlsplit(origin)
    expected_origin = f"{request.url.scheme}://{request.url.netloc}"
    actual_origin = f"{parsed.scheme}://{parsed.netloc}"
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or actual_origin != expected_origin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недопустимый источник запроса",
        )


SameOriginDep = Annotated[None, Depends(require_same_origin)]


def _unauthorized_session() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется вход",
        headers={"WWW-Authenticate": "Session"},
    )


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
