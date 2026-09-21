"""Вход, проверка и завершение пользовательских сессий."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from news_reposter.api.dependencies import (
    CSRF_AUTH_RESPONSES,
    SESSION_AUTH_RESPONSES,
    AuthContextDep,
    AuthenticationServiceDep,
    CsrfAuthContextDep,
    PasswordChangeServiceDep,
    SameOriginDep,
    UserSessionServiceDep,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.cookies import clear_auth_cookies, set_auth_cookies
from news_reposter.auth.passwords import PasswordValidationError
from news_reposter.config import get_settings
from news_reposter.schemas import (
    CurrentUserResponse,
    CurrentUserRole,
    LoginRequest,
    PasswordChangeRequest,
)
from news_reposter.services.authentication import (
    InvalidCredentialsError,
    LoginRateLimitedError,
)
from news_reposter.services.password_change import (
    CurrentPasswordInvalidError,
    PasswordChangeUserUnavailableError,
    PasswordUnchangedError,
)
from news_reposter.services.user_sessions import SessionRevocationReason

router = APIRouter(prefix="/auth", tags=["Авторизация"])
CACHE_CONTROL_NO_STORE = "no-store"

LOGIN_RESPONSES = {
    401: {"description": "Неверный логин или пароль"},
    403: {"description": "Недопустимый источник запроса"},
    429: {"description": "Слишком много попыток входа"},
}

PASSWORD_CHANGE_RESPONSES = {
    **CSRF_AUTH_RESPONSES,
    400: {"description": "Текущий пароль неверен или новый совпадает с ним"},
    422: {"description": "Новый пароль не соответствует политике безопасности"},
}


@router.post(
    "/login",
    response_model=CurrentUserResponse,
    responses=LOGIN_RESPONSES,
    summary="Войти в приложение",
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthenticationServiceDep,
    session_service: UserSessionServiceDep,
    _same_origin: SameOriginDep,
) -> CurrentUserResponse:
    """Проверяет пароль, создаёт серверную сессию и устанавливает cookie."""

    try:
        result = await auth_service.authenticate(
            username=payload.username,
            password=payload.password,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            request_id=getattr(request.state, "request_id", None),
        )
    except LoginRateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток входа. Повторите позже.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Session"},
        ) from exc

    created = result.created_session
    user_session = await session_service.validate(created.tokens.session_token)
    auth = AuthContext.from_session(user_session)
    settings = get_settings()
    set_auth_cookies(
        response,
        tokens=created.tokens,
        absolute_expires_at=created.session.absolute_expires_at,
        settings=settings,
    )
    response.headers["Cache-Control"] = CACHE_CONTROL_NO_STORE
    return _current_user_response(auth)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    responses=SESSION_AUTH_RESPONSES,
    summary="Получить текущего пользователя",
)
async def current_user(
    auth: AuthContextDep,
    response: Response,
) -> CurrentUserResponse:
    """Возвращает профиль, активные роли и актуальные разрешения сессии."""

    response.headers["Cache-Control"] = CACHE_CONTROL_NO_STORE
    return _current_user_response(auth)


@router.post(
    "/change-password",
    response_model=CurrentUserResponse,
    responses=PASSWORD_CHANGE_RESPONSES,
    summary="Сменить свой пароль",
)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    auth: CsrfAuthContextDep,
    password_change: PasswordChangeServiceDep,
    _same_origin: SameOriginDep,
) -> CurrentUserResponse:
    """Меняет пароль, отзывает старые сессии и обновляет текущую cookie."""

    try:
        result = await password_change.change(
            user_id=auth.user.user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except CurrentPasswordInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текущий пароль указан неверно",
        ) from exc
    except PasswordUnchangedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль должен отличаться от текущего",
        ) from exc
    except PasswordValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PasswordChangeUserUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход",
            headers={"WWW-Authenticate": "Session"},
        ) from exc

    created = result.created_session
    set_auth_cookies(
        response,
        tokens=created.tokens,
        absolute_expires_at=created.session.absolute_expires_at,
        settings=get_settings(),
    )
    response.headers["Cache-Control"] = CACHE_CONTROL_NO_STORE
    return _current_user_response(
        AuthContext(
            session=created.session,
            user=result.user,
            role_codes=auth.role_codes,
            permission_codes=auth.permission_codes,
        )
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=CSRF_AUTH_RESPONSES,
    summary="Выйти из текущей сессии",
)
async def logout(
    request: Request,
    auth: CsrfAuthContextDep,
    session_service: UserSessionServiceDep,
    _same_origin: SameOriginDep,
) -> Response:
    """Отзывает только текущую серверную сессию и удаляет её cookie."""

    settings = get_settings()
    session_token = request.cookies.get(settings.auth_session_cookie_name)
    if session_token is not None:
        await session_service.revoke(
            session_token,
            reason=SessionRevocationReason.LOGOUT,
        )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings=settings)
    response.headers["Cache-Control"] = CACHE_CONTROL_NO_STORE
    return response


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=CSRF_AUTH_RESPONSES,
    summary="Завершить все свои сессии",
)
async def logout_all(
    auth: CsrfAuthContextDep,
    session_service: UserSessionServiceDep,
    _same_origin: SameOriginDep,
) -> Response:
    """Отзывает все серверные сессии текущего пользователя, включая текущую."""

    await session_service.revoke_all_for_user(
        auth.user.user_id,
        reason=SessionRevocationReason.LOGOUT_ALL,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings=get_settings())
    response.headers["Cache-Control"] = CACHE_CONTROL_NO_STORE
    return response


def _current_user_response(auth: AuthContext) -> CurrentUserResponse:
    active_roles = sorted(
        (role for role in auth.user.roles if role.is_active),
        key=lambda role: role.code,
    )
    return CurrentUserResponse(
        user_id=auth.user.user_id,
        username=auth.user.username,
        display_name=auth.user.display_name,
        avatar_url=None,
        must_change_password=auth.user.must_change_password,
        roles=[
            CurrentUserRole(code=role.code, name=role.name) for role in active_roles
        ],
        permissions=sorted(auth.permission_codes),
    )
