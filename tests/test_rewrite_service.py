import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from news_reposter.llm import RewriteResult
from news_reposter.services.rewrite import RewriteService, RewriteServiceError


def make_item(*, text: str | None, prompt: str | None):
    return SimpleNamespace(
        post=SimpleNamespace(original_text=text),
        target=SimpleNamespace(rewrite_prompt=prompt),
    )


def test_rewrite_uses_target_prompt_when_present() -> None:
    provider = SimpleNamespace(
        rewrite=AsyncMock(
            return_value=RewriteResult(
                text="Готовый текст",
                provider="gigachat",
                model="GigaChat-2-Pro",
            )
        )
    )
    settings = SimpleNamespace(llm_default_rewrite_prompt="Общий промпт")
    service = RewriteService(provider, settings)

    result = asyncio.run(service.rewrite(make_item(text="Исходник", prompt="Промпт канала")))

    assert result.text == "Готовый текст"
    request = provider.rewrite.await_args.args[0]
    assert request.text == "Исходник"
    assert request.system_prompt == "Промпт канала"


def test_rewrite_falls_back_to_default_prompt() -> None:
    provider = SimpleNamespace(
        rewrite=AsyncMock(
            return_value=RewriteResult(text="Готово", provider="gigachat", model="model")
        )
    )
    service = RewriteService(provider, SimpleNamespace(llm_default_rewrite_prompt="Общий промпт"))

    asyncio.run(service.rewrite(make_item(text="Исходник", prompt=None)))

    request = provider.rewrite.await_args.args[0]
    assert request.system_prompt == "Общий промпт"


def test_rewrite_rejects_empty_source_text() -> None:
    service = RewriteService(
        SimpleNamespace(rewrite=AsyncMock()),
        SimpleNamespace(llm_default_rewrite_prompt="Общий промпт"),
    )

    with pytest.raises(RewriteServiceError, match="нет текста"):
        service.context_for(make_item(text="   ", prompt=None))
