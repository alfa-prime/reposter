import asyncio

import httpx
import pytest

from news_reposter.integrations.vk import VKAPIError, VKClient


def test_get_latest_post() -> None:
    """Проверяет разбор успешного ответа wall.get."""

    async def scenario() -> None:
        """Выполняет асинхронную часть проверки."""

        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Проверяет запрос и возвращает тестовый ответ VK."""

            nonlocal request_count
            request_count += 1

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
        assert request_count == 1

    asyncio.run(scenario())


def test_get_latest_post_skips_old_pinned_post() -> None:
    """Проверяет выбор свежего поста, если первым пришёл старый закреплённый."""

    async def scenario() -> None:
        """Выполняет асинхронную часть проверки."""

        offsets: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Возвращает запись с учётом смещения в запросе."""

            offsets.append(request.url.params.get("offset"))
            if request.url.params.get("offset") == "1":
                return httpx.Response(
                    200,
                    json={
                        "response": {
                            "count": 2,
                            "items": [
                                {
                                    "id": 11,
                                    "owner_id": -123,
                                    "date": 1_800_000_000,
                                    "text": "Новый пост",
                                }
                            ],
                        }
                    },
                )

            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 2,
                        "items": [
                            {
                                "id": 10,
                                "owner_id": -123,
                                "date": 1_700_000_000,
                                "text": "Старый закреплённый пост",
                                "is_pinned": 1,
                            }
                        ],
                    }
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = VKClient(access_token="secret", http_client=http_client)
            post = await client.get_latest_post("news_murmansk")

        assert post is not None
        assert post.id == 11
        assert post.text == "Новый пост"
        assert offsets == [None, "1"]

    asyncio.run(scenario())


def test_get_posts_after_returns_all_new_posts_in_chronological_order() -> None:
    """Проверяет получение всех постов после известного ID."""

    async def scenario() -> None:
        offsets: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            offset = request.url.params["offset"]
            offsets.append(offset)
            assert request.url.params["count"] == "100"

            if offset == "0":
                items = [
                    {
                        "id": 105,
                        "owner_id": -123,
                        "date": 1_800_000_005,
                        "text": "Пятый",
                    },
                    {
                        "id": 104,
                        "owner_id": -123,
                        "date": 1_800_000_004,
                        "text": "Четвёртый",
                    },
                    {
                        "id": 103,
                        "owner_id": -123,
                        "date": 1_800_000_003,
                        "text": "Третий",
                    },
                    {
                        "id": 102,
                        "owner_id": -123,
                        "date": 1_800_000_002,
                        "text": "Второй",
                    },
                    {
                        "id": 101,
                        "owner_id": -123,
                        "date": 1_800_000_001,
                        "text": "Первый",
                    },
                    {
                        "id": 100,
                        "owner_id": -123,
                        "date": 1_800_000_000,
                        "text": "Уже известный",
                    },
                ]
            else:
                items = []

            return httpx.Response(
                200,
                json={"response": {"count": len(items), "items": items}},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = VKClient(access_token="secret", http_client=http_client)
            posts = await client.get_posts_after("news_murmansk", 100)

        assert [post.id for post in posts] == [101, 102, 103, 104, 105]
        assert offsets == ["0"]

    asyncio.run(scenario())


def test_get_posts_after_skips_pinned_post() -> None:
    """Проверяет, что закреплённый старый пост не мешает сбору свежих записей."""

    async def scenario() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "response": {
                        "count": 4,
                        "items": [
                            {
                                "id": 50,
                                "owner_id": -123,
                                "date": 1_700_000_000,
                                "text": "Старый закреплённый",
                                "is_pinned": 1,
                            },
                            {
                                "id": 103,
                                "owner_id": -123,
                                "date": 1_800_000_003,
                                "text": "Новый 3",
                            },
                            {
                                "id": 102,
                                "owner_id": -123,
                                "date": 1_800_000_002,
                                "text": "Новый 2",
                            },
                            {
                                "id": 100,
                                "owner_id": -123,
                                "date": 1_800_000_000,
                                "text": "Известный",
                            },
                        ],
                    }
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = VKClient(access_token="secret", http_client=http_client)
            posts = await client.get_posts_after("news_murmansk", 100)

        assert [post.id for post in posts] == [102, 103]

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
