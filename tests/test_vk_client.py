import asyncio

import httpx
import pytest

from news_reposter.integrations.vk import VKAPIError, VKClient


def test_get_latest_post() -> None:
    """Проверяет разбор успешного ответа wall.get."""

    async def scenario() -> None:
        """Выполняет асинхронную часть проверки."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Проверяет запрос и возвращает тестовый ответ VK."""

            assert request.url.path.endswith("/wall.get")
            assert request.url.params["domain"] == "news_murmansk"
            assert request.url.params["count"] == "1"
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 1,
                        "items": [
                            {
                                "id": 42,
                                "owner_id": -123,
                                "from_id": -123,
                                "date": 1_700_000_000,
                                "text": "Тестовая новость",
                                "attachments": [{"type": "photo", "photo": {"id": 7}}],
                            }
                        ],
                    }
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = VKClient(access_token="secret", http_client=http_client)
            post = await client.get_latest_post("https://vk.com/news_murmansk")

        assert post is not None
        assert post.id == 42
        assert post.text == "Тестовая новость"
        assert post.source_url == "https://vk.com/wall-123_42"

    asyncio.run(scenario())


def test_vk_api_error() -> None:
    """Проверяет преобразование ошибки VK в исключение клиента."""

    async def scenario() -> None:
        """Выполняет асинхронную часть проверки."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Возвращает ошибку VK с успешным HTTP-статусом."""

            return httpx.Response(
                200,
                json={"error": {"error_code": 5, "error_msg": "User authorization failed"}},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = VKClient(access_token="bad-token", http_client=http_client)
            with pytest.raises(VKAPIError) as error:
                await client.get_latest_post("club123")

        assert error.value.code == 5

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("group", "expected"),
    [
        ("club123", {"owner_id": -123}),
        ("public123", {"owner_id": -123}),
        ("-123", {"owner_id": -123}),
        ("https://vk.com/news_murmansk", {"domain": "news_murmansk"}),
        ("https://vk.ru/peninsula51", {"domain": "peninsula51"}),
        ("https://m.vk.ru/peninsula51/", {"domain": "peninsula51"}),
    ],
)
def test_group_parameter(group: str, expected: dict[str, str | int]) -> None:
    """Проверяет разные варианты адреса и идентификатора группы."""

    assert VKClient._group_parameter(group) == expected
