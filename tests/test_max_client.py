import asyncio
import json

import httpx
import pytest

from news_reposter.integrations.max import MAXAPIError, MAXClient


def test_publish_post_with_images() -> None:
    """Проверяет отправку текста и фотографий в канал MAX."""

    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
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
                "format": "markdown",
            }
            return httpx.Response(
                200,
                json={"message": {"url": "https://max.ru/channel/post"}},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
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


def test_upload_video_returns_token() -> None:
    """Проверяет двухшаговую загрузку видео через /uploads MAX."""

    async def scenario() -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path == "/uploads":
                assert request.url.params["type"] == "video"
                return httpx.Response(
                    200,
                    json={
                        "url": "https://upload.example/video",
                        "token": "video-token",
                    },
                )
            if request.url.host == "upload.example":
                assert b"movie.mp4" in request.content
                return httpx.Response(200, json={"retval": {"ok": True}})
            return httpx.Response(404)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = MAXClient(access_token="secret", http_client=http_client)
            token = await client.upload_media(
                media_type="video",
                filename="movie.mp4",
                content=b"video-bytes",
                content_type="video/mp4",
            )

        assert token == "video-token"
        assert calls == ["/uploads", "/video"]

    asyncio.run(scenario())


def test_upload_video_uses_initial_token_when_upload_response_is_not_json() -> None:
    """Успешная загрузка видео может вернуть не-JSON, token уже выдан /uploads."""

    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/uploads":
                return httpx.Response(
                    200,
                    json={
                        "url": "https://upload.example/video",
                        "token": "video-token-from-uploads",
                    },
                )
            if request.url.host == "upload.example":
                return httpx.Response(200, text="OK")
            return httpx.Response(404)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = MAXClient(access_token="secret", http_client=http_client)
            token = await client.upload_media(
                media_type="video",
                filename="movie.mp4",
                content=b"video-bytes",
                content_type="video/mp4",
            )

        assert token == "video-token-from-uploads"

    asyncio.run(scenario())


def test_get_updates() -> None:
    """Проверяет получение событий MAX через Long Polling."""

    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/updates"
            assert request.headers["Authorization"] == "secret"
            assert request.url.params["limit"] == "10"
            assert request.url.params["timeout"] == "0"
            assert request.url.params["marker"] == "123"
            assert request.url.params["types"] == "bot_added,bot_started"
            return httpx.Response(
                200,
                json={
                    "updates": [
                        {"update_type": "bot_added", "chat_id": -77162942582085}
                    ],
                    "marker": 124,
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = MAXClient(access_token="secret", http_client=http_client)
            result = await client.get_updates(
                limit=10,
                timeout=0,
                marker=123,
                types=["bot_added", "bot_started"],
            )

        assert result["marker"] == 124
        assert result["updates"][0]["chat_id"] == -77162942582085

    asyncio.run(scenario())


def test_get_subscriptions() -> None:
    """Проверяет запрос webhook-подписок MAX."""

    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/subscriptions"
            assert request.headers["Authorization"] == "secret"
            return httpx.Response(200, json={"subscriptions": []})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = MAXClient(access_token="secret", http_client=http_client)
            result = await client.get_subscriptions()

        assert result == {"subscriptions": []}

    asyncio.run(scenario())


def test_create_subscription_and_get_chat() -> None:
    """Проверяет создание webhook-подписки и чтение данных канала."""

    async def scenario() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/subscriptions":
                assert request.method == "POST"
                assert request.headers["Authorization"] == "secret"
                assert json.loads(request.content) == {
                    "url": "https://www.uncle-vlad.ru/api/v1/max/webhook",
                    "secret": "test_secret_123",
                    "update_types": ["bot_added", "bot_removed"],
                }
                return httpx.Response(200, json={"success": True})
            if request.url.path == "/chats/-77162942582085":
                return httpx.Response(
                    200,
                    json={
                        "chat_id": -77162942582085,
                        "type": "channel",
                        "title": "Новости 51",
                        "link": "https://max.ru/channel_51_news",
                    },
                )
            return httpx.Response(404)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = MAXClient(access_token="secret", http_client=http_client)
            subscription = await client.create_subscription(
                url="https://www.uncle-vlad.ru/api/v1/max/webhook",
                secret="test_secret_123",
                update_types=["bot_added", "bot_removed"],
            )
            chat = await client.get_chat(-77162942582085)

        assert subscription["success"] is True
        assert chat["chat_id"] == -77162942582085
        assert chat["link"] == "https://max.ru/channel_51_news"
        assert len(requests) == 2

    asyncio.run(scenario())


def test_max_api_error() -> None:
    """Проверяет преобразование HTTP-ошибки MAX в исключение клиента."""

    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "access denied"})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
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
