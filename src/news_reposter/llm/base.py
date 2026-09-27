from dataclasses import dataclass, field
from typing import Protocol


class LLMProviderError(RuntimeError):
    """Ошибка взаимодействия с провайдером LLM."""

    def __init__(
        self, message: str, *, retryable: bool = False, retry_after: float | None = None
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass(slots=True)
class RewriteRequest:
    """Нейтральный запрос на рерайт, не зависящий от конкретного LLM-провайдера."""

    text: str
    system_prompt: str
    temperature: float = 0.4
    max_tokens: int = 2048


@dataclass(slots=True)
class RewriteResult:
    """Результат рерайта в общем формате приложения."""

    text: str
    provider: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(Protocol):
    """Контракт LLM-провайдера, который использует бизнес-логика приложения."""

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Переписывает текст в соответствии с системным промптом."""
