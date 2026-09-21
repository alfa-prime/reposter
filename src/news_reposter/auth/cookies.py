"""Единая безопасная политика cookie пользовательской сессии."""

from datetime import datetime

from fastapi import Response

from news_reposter.auth.session_tokens import SessionTokens
from news_reposter.config import Settings

COOKIE_PATH = "/"
COOKIE_SAME_SITE = "strict"


def set_auth_cookies(
    response: Response,
    *,
    tokens: SessionTokens,
    absolute_expires_at: datetime,
    settings: Settings,
) -> None:
    """Записывает сессию и CSRF-токен без раскрытия их в теле ответа."""

    max_age = settings.auth_session_absolute_hours * 60 * 60
    common = {
        "max_age": max_age,
        "expires": absolute_expires_at,
        "path": COOKIE_PATH,
        "secure": settings.auth_cookie_secure,
        "samesite": COOKIE_SAME_SITE,
    }
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=tokens.session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=tokens.csrf_token,
        httponly=False,
        **common,
    )


def clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    """Удаляет обе cookie с теми же атрибутами, с которыми они созданы."""

    common = {
        "path": COOKIE_PATH,
        "secure": settings.auth_cookie_secure,
        "samesite": COOKIE_SAME_SITE,
    }
    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        httponly=True,
        **common,
    )
    response.delete_cookie(
        key=settings.auth_csrf_cookie_name,
        httponly=False,
        **common,
    )
