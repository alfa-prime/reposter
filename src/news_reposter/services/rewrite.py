from dataclasses import dataclass

from news_reposter.config import Settings, get_settings
from news_reposter.db.models import QueueItem
from news_reposter.llm import LLMProvider, RewriteRequest, RewriteResult


class RewriteServiceError(RuntimeError):
    """Ошибка подготовки конкретного элемента очереди к рерайту."""


@dataclass(slots=True)
class RewriteContext:
    """Контекст рерайта, уже разрешённый из очереди и канала."""

    source_text: str
    system_prompt: str


class RewriteService:
    """Оркестрирует рерайт независимо от конкретного LLM-провайдера."""

    def __init__(self, provider: LLMProvider, settings: Settings | None = None) -> None:
        self.provider = provider
        self.settings = settings or get_settings()

    def context_for(self, item: QueueItem) -> RewriteContext:
        post = getattr(item, "post", None)
        target = getattr(item, "target", None)
        source_text = (getattr(post, "original_text", None) or "").strip()
        if not source_text:
            raise RewriteServiceError("У исходного поста нет текста для рерайта")

        target_prompt = (getattr(target, "rewrite_prompt", None) or "").strip()
        system_prompt = target_prompt or self.settings.llm_default_rewrite_prompt.strip()
        if not system_prompt:
            raise RewriteServiceError("Не настроена инструкция для рерайта")

        return RewriteContext(source_text=source_text, system_prompt=system_prompt)

    async def rewrite(self, item: QueueItem) -> RewriteResult:
        context = self.context_for(item)
        return await self.provider.rewrite(
            RewriteRequest(
                text=context.source_text,
                system_prompt=context.system_prompt,
            )
        )
