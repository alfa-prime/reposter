from news_reposter.config import Settings, get_settings

from .base import LLMProvider
from .gigachat import GigaChatProvider


def build_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Создаёт настроенный LLM-провайдер приложения."""

    config = settings or get_settings()
    provider = config.llm_provider.strip().lower()

    if provider == "gigachat":
        if not config.gigachat_credentials:
            raise RuntimeError("Для GigaChat не задан GIGACHAT_CREDENTIALS")
        return GigaChatProvider(
            credentials=config.gigachat_credentials,
            scope=config.gigachat_scope,
            model=config.gigachat_model,
            api_url=config.gigachat_api_url,
            auth_url=config.gigachat_auth_url,
            ca_file=config.gigachat_ca_file,
            timeout=config.llm_timeout_seconds,
        )

    raise RuntimeError(f"Неизвестный LLM-провайдер: {config.llm_provider}")
