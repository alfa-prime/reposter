import asyncio
import time

import httpx

from news_reposter.llm import RewriteRequest
from news_reposter.llm.gigachat import GigaChatProvider


def test_gigachat_rewrite_gets_token_and_reuses_it() -> None:
    auth_calls = 0
    completion_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal auth_calls, completion_calls

        if request.url.path == "/api/v2/oauth":
            auth_calls += 1
            assert request.headers["Authorization"] == "Basic test-credentials"
            assert request.headers.get("RqUID")
            assert b"scope=GIGACHAT_API_PERS" in request.content
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "expires_at": int((time.time() + 1800) * 1000),
                },
            )

        if request.url.path == "/v1/chat/completions":
            completion_calls += 1
            assert request.headers["Authorization"] == "Bearer access-token"
            body = __import__("json").loads(request.content)
            assert body["model"] == "GigaChat-2-Pro"
            assert body["messages"][0] == {
                "role": "system",
                "content": "Перепиши новость",
            }
            assert body["messages"][1] == {"role": "user", "content": "Исходный текст"}
            return httpx.Response(
                200,
                json={
                    "model": "GigaChat-2-Pro",
                    "choices": [{"message": {"content": "Готовый рерайт"}}],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 8,
                        "total_tokens": 20,
                    },
                },
            )

        return httpx.Response(404)

    provider = GigaChatProvider(
        credentials="test-credentials",
        scope="GIGACHAT_API_PERS",
        model="GigaChat-2-Pro",
        api_url="https://api.giga.chat/v1",
        auth_url="https://auth.example/api/v2/oauth",
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        request = RewriteRequest(
            text="Исходный текст", system_prompt="Перепиши новость"
        )
        first = await provider.rewrite(request)
        second = await provider.rewrite(request)

        assert first.text == "Готовый рерайт"
        assert first.provider == "gigachat"
        assert first.model == "GigaChat-2-Pro"
        assert first.usage["total_tokens"] == 20
        assert second.text == "Готовый рерайт"

    asyncio.run(run())

    assert auth_calls == 1
    assert completion_calls == 2
