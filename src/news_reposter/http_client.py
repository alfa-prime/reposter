"""Общий асинхронный HTTP-клиент приложения."""

import ssl

import httpx

from news_reposter.config import Settings, get_settings


def create_http_ssl_context(ca_file: str | None = None) -> ssl.SSLContext:
    """Создаёт TLS-контекст и при необходимости добавляет доверенный CA-файл."""

    context = ssl.create_default_context()
    if ca_file:
        try:
            context.load_verify_locations(cafile=ca_file)
        except OSError as exc:
            raise RuntimeError(f"Не удалось загрузить HTTP_CA_FILE: {ca_file}") from exc
    return context


def create_http_client(settings: Settings | None = None) -> httpx.AsyncClient:
    """Создаёт клиент с общим пулом соединений на время жизни приложения.

    Авторизация внешних сервисов намеренно не задаётся здесь: VK, MAX,
    Telegram и LLM-провайдеры должны передавать свои токены в каждом запросе.
    Это позволяет безопасно использовать один пул для разных интеграций.
    """

    resolved_settings = settings or get_settings()
    ssl_context = create_http_ssl_context(resolved_settings.http_ca_file)
    timeout = httpx.Timeout(
        resolved_settings.http_timeout_seconds,
        connect=resolved_settings.http_connect_timeout_seconds,
    )
    limits = httpx.Limits(
        max_connections=resolved_settings.http_max_connections,
        max_keepalive_connections=(resolved_settings.http_max_keepalive_connections),
        keepalive_expiry=resolved_settings.http_keepalive_expiry_seconds,
    )
    return httpx.AsyncClient(
        verify=ssl_context,
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
        headers={"User-Agent": "news-reposter/0.1.0"},
        trust_env=resolved_settings.http_trust_env,
    )
