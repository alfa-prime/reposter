"""Нормализация и проверка идентификаторов пользователя."""

from dataclasses import dataclass
from re import fullmatch
from unicodedata import normalize


class IdentityValidationError(ValueError):
    """Логин или отображаемое имя не прошли проверку."""


@dataclass(frozen=True, slots=True)
class PreparedUsername:
    """Безопасное представление логина для сохранения и поиска."""

    value: str
    normalized: str


def prepare_username(value: str) -> PreparedUsername:
    """Нормализует логин и проверяет его стабильный ASCII-формат."""

    prepared = normalize("NFKC", value).strip()
    normalized = prepared.casefold()

    if not 3 <= len(normalized) <= 64:
        raise IdentityValidationError("Логин должен содержать от 3 до 64 символов")
    if fullmatch(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?", normalized) is None:
        raise IdentityValidationError(
            "Логин может содержать латинские буквы, цифры, точки, дефисы и "
            "подчёркивания; первый и последний символы должны быть буквой или цифрой"
        )

    return PreparedUsername(value=prepared, normalized=normalized)


def prepare_display_name(value: str) -> str:
    """Нормализует имя, которое будет показано в интерфейсе."""

    prepared = normalize("NFKC", value).strip()
    if not 1 <= len(prepared) <= 200:
        raise IdentityValidationError(
            "Отображаемое имя должно содержать от 1 до 200 символов"
        )
    return prepared
