import re
from urllib.parse import urlparse

import httpx

from news_reposter.integrations.vk.schemas import VKPost, VKWallEnvelope


class VKAPIError(RuntimeError):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class VKClient:
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

    async def get_latest_post(self, group: str) -> VKPost | None:
        params: dict[str, str | int] = {
            "access_token": self._access_token,
            "v": self._api_version,
            "count": 1,
            "filter": "owner",
        }
        params.update(self._group_parameter(group))

        if self._http_client is not None:
            return await self._request_latest(self._http_client, params)

        async with httpx.AsyncClient(timeout=15.0) as client:
            return await self._request_latest(client, params)

    async def _request_latest(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str | int],
    ) -> VKPost | None:
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

        if envelope.response is None or not envelope.response.items:
            return None

        return envelope.response.items[0]

    @staticmethod
    def _group_parameter(group: str) -> dict[str, str | int]:
        value = group.strip().rstrip("/")
        if not value:
            raise ValueError("Группа VK не указана")

        if "://" in value:
            parsed = urlparse(value)
            if parsed.netloc not in {"vk.com", "www.vk.com", "m.vk.com"}:
                raise ValueError("Ожидается ссылка на vk.com")
            value = parsed.path.strip("/").split("/", maxsplit=1)[0]

        numeric_match = re.fullmatch(r"(?:club|public|event)?(-?\d+)", value)
        if numeric_match:
            group_id = abs(int(numeric_match.group(1)))
            return {"owner_id": -group_id}

        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Некорректное короткое имя группы VK")

        return {"domain": value}

