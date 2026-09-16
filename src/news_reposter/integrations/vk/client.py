import re
from urllib.parse import urlparse

import httpx

from news_reposter.integrations.vk.schemas import VKPost, VKWallEnvelope


class VKAPIError(RuntimeError):
    """Ошибка, полученная при обращении к API VK."""

    def __init__(self, message: str, code: int | None = None) -> None:
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
        self._access_token = access_token
        self._api_version = api_version
        self._api_url = api_url.rstrip("/")
        self._http_client = http_client

    async def get_group_info(self, group: str) -> dict[str, object]:
        """Возвращает название и аватар сообщества VK по ссылке/домену/ID."""
        identifier = self._group_identifier(group)
        params = {
            "access_token": self._access_token,
            "v": self._api_version,
            "group_ids": identifier,
            "fields": "photo_100,screen_name",
        }
        if self._http_client is not None:
            return await self._request_group_info(self._http_client, params)
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await self._request_group_info(client, params)

    async def _request_group_info(
        self, client: httpx.AsyncClient, params: dict[str, str]
    ) -> dict[str, object]:
        try:
            response = await client.get(
                f"{self._api_url}/groups.getById", params=params
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VKAPIError(f"Не удалось выполнить запрос к VK: {exc}") from exc
        payload = response.json()
        error = payload.get("error")
        if error:
            raise VKAPIError(
                error.get("error_msg", "VK вернул ошибку"), error.get("error_code")
            )

        response_data = payload.get("response") or []
        groups = (
            response_data.get("groups", [])
            if isinstance(response_data, dict)
            else response_data
        )
        if not groups:
            raise VKAPIError("Сообщество VK не найдено")
        return groups[0]

    async def get_latest_post(self, group: str) -> VKPost | None:
        params = self._base_wall_params(group)
        params["count"] = 1
        if self._http_client is not None:
            return await self._request_latest(self._http_client, params)
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await self._request_latest(client, params)

    async def get_posts_after(self, group: str, after_post_id: int) -> list[VKPost]:
        params = self._base_wall_params(group)
        params["count"] = 100
        if self._http_client is not None:
            return await self._request_posts_after(
                self._http_client, params, after_post_id
            )
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await self._request_posts_after(client, params, after_post_id)

    async def _request_latest(
        self, client: httpx.AsyncClient, params: dict[str, str | int]
    ) -> VKPost | None:
        post = await self._request_post(client, params)
        if post is None or post.is_pinned != 1:
            return post
        next_post = await self._request_post(client, {**params, "offset": 1})
        return next_post or post

    async def _request_posts_after(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
        after_post_id: int,
    ) -> list[VKPost]:
        offset = 0
        page_size = int(params["count"])
        collected: list[VKPost] = []
        while True:
            envelope = await self._request_wall(client, {**params, "offset": offset})
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
            if reached_known_post:
                break

            # VK трактует offset как смещение обычных записей стены. Закреплённая
            # запись может дополнительно присутствовать на первой странице,
            # поэтому увеличивать offset на len(items) небезопасно: так можно
            # пропустить одну запись. Двигаемся ровно на запрошенный размер.
            offset += page_size
            if offset >= envelope.response.count:
                break
        collected.sort(key=lambda post: post.id)
        return collected

    async def _request_post(
        self, client: httpx.AsyncClient, params: dict[str, str | int]
    ) -> VKPost | None:
        envelope = await self._request_wall(client, params)
        if envelope.response is None or not envelope.response.items:
            return None
        return envelope.response.items[0]

    async def _request_wall(
        self, client: httpx.AsyncClient, params: dict[str, str | int]
    ) -> VKWallEnvelope:
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
        params: dict[str, str | int] = {
            "access_token": self._access_token,
            "v": self._api_version,
            "filter": "owner",
        }
        params.update(self._group_parameter(group))
        return params

    @staticmethod
    def _group_identifier(group: str) -> str:
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
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Некорректное короткое имя группы VK")
        numeric_alias = re.fullmatch(r"(?:club|public|event)(\d+)", value)
        return numeric_alias.group(1) if numeric_alias else value

    @staticmethod
    def _group_parameter(group: str) -> dict[str, str | int]:
        value = VKClient._group_identifier(group)
        numeric_match = re.fullmatch(r"-?\d+", value)
        if numeric_match:
            return {"owner_id": -abs(int(numeric_match.group(0)))}
        return {"domain": value}
