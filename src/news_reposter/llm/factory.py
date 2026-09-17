import httpx

from news_reposter.config import Settings, get_settings

from .base import LLMProvider
from .gigachat import GigaChatProvider


def build_llm_provider(
    http_client: httpx.AsyncClient,
    settings: Settings | None = None,
) -> LLMProvider:
    """Создаёт LLM-провайдер по переданным настройкам."""

    config = settings or get_settings()
    provider = config.llm_provider.strip().lower()

    if provider == "gigachat":
        if not config.gigachat_credentials:
            raise RuntimeError("Для GigaChat не задан GIGACHAT_CREDENTIALS")
        return GigaChatProvider(
            credentials=config.gigachat_credentials,
            http_client=http_client,
            scope=config.gigachat_scope,
            model=config.gigachat_model,
            api_url=config.gigachat_api_url,
            auth_url=config.gigachat_auth_url,
            timeout=config.llm_timeout_seconds,
        )

    raise RuntimeError(f"Неизвестный LLM-провайдер: {config.llm_provider}")
