import asyncio
import json

import httpx
import pytest

from news_reposter.integrations.max import MAXAPIError, MAXClient


def test_publish_post_with_images() -> None:
    """Проверяет отправку текста и фотографий в канал MAX."""

    async def scenario() -> None:
        """Выполняет асинхронную часть проверки."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Проверяет запрос и возвращает тестовый ответ MAX."""

            assert request.url.path == "/messages"
            assert request.url.params["chat_id"] == "-77162942582085"
            assert request.headers["Authorization"] == "secret"
            assert json.loads(request.content) == {
                "text": "Тестовая новость",
                "attachments": [
                    {
                        "type": "image",
                        "payload": {"url": "https://example.com/photo.jpg"},
                    }
                ],
            }
            return httpx.Response(
                200,
                json={"message": {"url": "https://max.ru/channel/post"}},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = MAXClient(
                access_token="secret",
                chat_id=-77162942582085,
                http_client=http_client,
            )
            result = await client.publish_post(
                text="Тестовая новость",
                image_urls=["https://example.com/photo.jpg"],
            )

        assert result["message"]["url"] == "https://max.ru/channel/post"

    asyncio.run(scenario())


def test_max_api_error() -> None:
    """Проверяет преобразование HTTP-ошибки MAX в исключение клиента."""

    async def scenario() -> None:
        """Выполняет асинхронную часть проверки."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Возвращает отказ в доступе от MAX."""

            return httpx.Response(403, json={"message": "access denied"})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = MAXClient(
                access_token="secret",
                chat_id=-1,
                http_client=http_client,
            )
            with pytest.raises(MAXAPIError) as error:
                await client.publish_post(text="Новость")

        assert error.value.status_code == 403

    asyncio.run(scenario())
