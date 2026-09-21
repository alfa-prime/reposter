"""Нормализация необязательных данных клиентского запроса."""

from ipaddress import ip_address


def normalize_client_ip(value: str | None) -> str | None:
    """Возвращает канонический IPv4/IPv6 или None для недостоверного значения."""

    if not value:
        return None
    try:
        return str(ip_address(value))
    except ValueError:
        return None


def normalize_user_agent(value: str | None) -> str | None:
    """Ограничивает диагностический User-Agent размером поля БД."""

    if not value:
        return None
    return value[:512]


def normalize_request_id(value: str | None) -> str | None:
    """Ограничивает корреляционный ID размером поля журнала входов."""

    if not value:
        return None
    return value[:64]
