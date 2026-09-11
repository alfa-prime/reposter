import re
from urllib.parse import urlparse

import httpx

from news_reposter.integrations.vk.schemas import VKPost, VKWallEnvelope


class VKAPIError(RuntimeError):
    """Ошибка, полученная при обращении к API VK."""

    def __init__(self, message: str, code: int | None = None) -> None:
        """Сохраняет сообщение и код ошибки VK, если он есть в ответе."""

        super().__init__(message)
        self.code = code


class VKClient:
    """Асинхронный клиент для чтения постов через VK API."""

    def __init__(
        self,
        *,
        access_token: str,
        api_version: str = "5.199",
        api_url: str = "https://api.vk.com/method",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Создаёт клиент с токеном и необязательной готовой HTTP-сессией."""

        self._access_token = access_token
        self._api_version = api_version
        self._api_url = api_url.rstrip("/")
        self._http_client = http_client

    async def get_latest_post(self, group: str) -> VKPost | None:
        """Возвращает последний пост, опубликованный от имени группы."""

        params = self._base_wall_params(group)
        params["count"] = 1

        if self._http_client is not None:
            return await self._request_latest(self._http_client, params)

        async with httpx.AsyncClient(timeout=15.0) as client:
            return await self._request_latest(client, params)

    async def get_posts_after(self, group: str, after_post_id: int) -> list[VKPost]:
        """Возвращает все обычные посты с ID больше указанного.

        VK отдаёт записи от новых к старым. Клиент читает стену страницами по 100
        записей, пока не встретит уже известный пост, а результат возвращает в
        хронологическом порядке — от старого к новому.
        """

        params = self._base_wall_params(group)
        params["count"] = 100

        if self._http_client is not None:
            return await self._request_posts_after(
                self._http_client,
                params,
                after_post_id,
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            return await self._request_posts_after(client, params, after_post_id)

    async def _request_latest(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
    ) -> VKPost | None:
        """Возвращает первую обычную запись, пропуская закреплённую."""

        post = await self._request_post(client, params)
        if post is None or post.is_pinned != 1:
            return post

        # Второй запрос нужен только для стены с закреплённой записью.
        next_post = await self._request_post(client, {**params, "offset": 1})
        return next_post or post

    async def _request_posts_after(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
        after_post_id: int,
    ) -> list[VKPost]:
        """Читает wall.get страницами до уже известного идентификатора."""

        offset = 0
        collected: list[VKPost] = []

        while True:
            envelope = await self._request_wall(
                client,
                {**params, "offset": offset},
            )
            if envelope.response is None or not envelope.response.items:
                break

            items = envelope.response.items
            reached_known_post = False
            for post in items:
                if post.is_pinned == 1:
                    continue
                if post.id <= after_post_id:
                    reached_known_post = True
                    break
                collected.append(post)

            if reached_known_post or len(items) < int(params["count"]):
                break
            offset += len(items)

        collected.sort(key=lambda post: post.id)
        return collected

    async def _request_post(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
    ) -> VKPost | None:
        """Выполняет wall.get и преобразует первую запись в модель поста."""

        envelope = await self._request_wall(client, params)
        if envelope.response is None or not envelope.response.items:
            return None
        return envelope.response.items[0]

    async def _request_wall(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
    ) -> VKWallEnvelope:
        """Выполняет wall.get и проверяет HTTP- и VK-ошибки."""

        try:
            response = await client.get(f"{self._api_url}/wall.get", params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VKAPIError(f"Не удалось выполнить запрос к VK: {exc}") from exc

        envelope = VKWallEnvelope.model_validate(response.json())
        if envelope.error:
            raise VKAPIError(
                message=envelope.error.get("error_msg", "VK вернул ошибку"),
                code=envelope.error.get("error_code"),
            )
        return envelope

    def _base_wall_params(self, group: str) -> dict[str, str | int]:
        """Формирует общие параметры wall.get для одного источника."""

        params: dict[str, str | int] = {
            "access_token": self._access_token,
            "v": self._api_version,
            # Посты посетителей стены для репостера не нужны.
            "filter": "owner",
        }
        params.update(self._group_parameter(group))
        return params

    @staticmethod
    def _group_parameter(group: str) -> dict[str, str | int]:
        """Преобразует ссылку, короткое имя или ID в параметры wall.get."""

        value = group.strip().rstrip("/")
        if not value:
            raise ValueError("Группа VK не указана")

        if "://" in value:
            parsed = urlparse(value)
            allowed_hosts = {
                "vk.com",
                "www.vk.com",
                "m.vk.com",
                "vk.ru",
                "www.vk.ru",
                "m.vk.ru",
            }
            if parsed.netloc.lower() not in allowed_hosts:
                raise ValueError("Ожидается ссылка на vk.ru или vk.com")
            value = parsed.path.strip("/").split("/", maxsplit=1)[0]

        numeric_match = re.fullmatch(r"(?:club|public|event)?(-?\d+)", value)
        if numeric_match:
            # Для сообществ VK ожидает отрицательный owner_id.
            group_id = abs(int(numeric_match.group(1)))
            return {"owner_id": -group_id}

        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Некорректное короткое имя группы VK")

        return {"domain": value}
