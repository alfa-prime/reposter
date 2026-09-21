"""Необратимые идентификаторы для защиты формы входа."""

import hashlib
from ipaddress import ip_address
from unicodedata import normalize


def username_fingerprint(username: str) -> bytes:
    """Создаёт стабильный отпечаток логина без сохранения исходной строки."""

    canonical = normalize("NFKC", username).strip().casefold()
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def username_lock_key(fingerprint: bytes) -> int:
    """Возвращает PostgreSQL advisory-lock key для одного логина."""

    return _advisory_lock_key(b"login:username", fingerprint)


def ip_lock_key(client_ip: str) -> int:
    """Возвращает PostgreSQL advisory-lock key для канонического IP."""

    return _advisory_lock_key(b"login:ip", ip_address(client_ip).packed)


def _advisory_lock_key(namespace: bytes, identity: bytes) -> int:
    digest = hashlib.sha256(namespace + b"\0" + identity).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)
