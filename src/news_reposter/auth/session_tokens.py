"""Создание и проверка непрозрачных токенов серверной сессии."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field

TOKEN_ENTROPY_BYTES = 32


@dataclass(frozen=True, slots=True)
class SessionTokens:
    """Секреты, которые передаются клиенту только при создании сессии."""

    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)


def generate_token() -> str:
    """Возвращает URL-safe токен с 256 битами энтропии."""

    return secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)


def generate_session_tokens() -> SessionTokens:
    """Создаёт независимые токены сессии и CSRF-защиты."""

    return SessionTokens(
        session_token=generate_token(),
        csrf_token=generate_token(),
    )


def hash_token(token: str) -> bytes:
    """Преобразует секретный токен в сохраняемый SHA-256 отпечаток."""

    if not token:
        raise ValueError("Токен не может быть пустым")
    return hashlib.sha256(token.encode("utf-8")).digest()


def token_matches(token: str, expected_hash: bytes) -> bool:
    """Сравнивает токен с отпечатком за постоянное время."""

    if len(expected_hash) != hashlib.sha256().digest_size:
        return False
    try:
        actual_hash = hash_token(token)
    except ValueError:
        return False
    return hmac.compare_digest(actual_hash, expected_hash)
