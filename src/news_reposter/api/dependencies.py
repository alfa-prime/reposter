from collections.abc import Awaitable, Callable
from secrets import compare_digest
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.auth.session_tokens import token_matches
from news_reposter.config import get_settings
from news_reposter.db.session import get_db_session
from news_reposter.llm import LLMProvider
from news_reposter.llm.factory import build_llm_provider
from news_reposter.services.authentication import AuthenticationService
from news_reposter.services.avatars import AvatarService
from news_reposter.services.password_change import PasswordChangeService
from news_reposter.services.user_sessions import (
    InvalidSessionError,
    UserSessionService,
)
from news_reposter.services.users import UserService

SESSION_AUTH_RESPONSES = {
    401: {"description": "Требуется действующая пользовательская сессия"},
}

PERMISSION_AUTH_RESPONSES = {
    **SESSION_AUTH_RESPONSES,
    403: {"description": "Недостаточно прав или требуется смена временного пароля"},
}

CSRF_AUTH_RESPONSES = {
    **SESSION_AUTH_RESPONSES,
    403: {"description": "Недействительный CSRF-токен или источник запроса"},
}

PERMISSION_CSRF_AUTH_RESPONSES = {
    **SESSION_AUTH_RESPONSES,
    403: {
        "description": (
            "Недостаточно прав, требуется смена временного пароля либо "
            "недействителен CSRF-токен или источник запроса"
        )
    },
}


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


def get_password_change_service(session: DbSessionDep) -> PasswordChangeService:
    """Создаёт сервис атомарной смены пароля текущего пользователя."""

    return PasswordChangeService(session)


PasswordChangeServiceDep = Annotated[
    PasswordChangeService,
    Depends(get_password_change_service),
]


def get_user_service(session: DbSessionDep) -> UserService:
    """Создаёт сервис административного управления пользователями."""

    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_avatar_service(session: DbSessionDep) -> AvatarService:
    """Создаёт сервис пользовательских аватаров для текущего запроса."""

    return AvatarService(session)


AvatarServiceDep = Annotated[AvatarService, Depends(get_avatar_service)]

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


def require_permission(
    permission: PermissionCode,
) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    """Создаёт FastAPI-зависимость для проверки одного разрешения.

    Код разрешения задаётся через ``PermissionCode``, поэтому опечатка в имени
    права не сможет незаметно закрыть или открыть endpoint. Актуальный набор
    прав берётся из ``AuthContext`` и, следовательно, из базы при каждом
    запросе.
    """

    async def permission_dependency(auth: AuthContextDep) -> AuthContext:
        if auth.user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Требуется сменить временный пароль",
            )
        if permission.value not in auth.permission_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав",
            )
        return auth

    return permission_dependency


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
