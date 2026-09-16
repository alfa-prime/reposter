import logging
import time
from dataclasses import dataclass

from news_reposter.config import Settings, get_settings
from news_reposter.db.models import QueueItem
from news_reposter.llm import LLMProvider, RewriteRequest, RewriteResult

logger = logging.getLogger(__name__)


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
        system_prompt = (
            target_prompt or self.settings.llm_default_rewrite_prompt.strip()
        )
        if not system_prompt:
            raise RewriteServiceError("Не настроена инструкция для рерайта")

        return RewriteContext(source_text=source_text, system_prompt=system_prompt)

    async def rewrite(self, item: QueueItem) -> RewriteResult:
        context = self.context_for(item)
        started_at = time.perf_counter()
        provider_name = str(
            getattr(self.provider, "name", type(self.provider).__name__)
        )
        queue_item_id = getattr(item, "queue_item_id", None)
        target_id = getattr(item, "target_id", None)

        try:
            result = await self.provider.rewrite(
                RewriteRequest(
                    text=context.source_text,
                    system_prompt=context.system_prompt,
                )
            )
        except Exception as exc:
            logger.warning(
                "action=rewrite status=failed queue_item_id=%s target_id=%s provider=%s duration_ms=%s error_type=%s",
                queue_item_id,
                target_id,
                provider_name,
                round((time.perf_counter() - started_at) * 1000),
                type(exc).__name__,
            )
            raise

        logger.info(
            "action=rewrite status=success queue_item_id=%s target_id=%s provider=%s model=%s duration_ms=%s total_tokens=%s",
            queue_item_id,
            target_id,
            result.provider,
            result.model,
            round((time.perf_counter() - started_at) * 1000),
            result.usage.get("total_tokens", 0),
        )
        return result
