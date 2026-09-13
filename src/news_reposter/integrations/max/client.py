import ssl
from typing import Any

import httpx


class MAXAPIError(RuntimeError):
    """Ошибка при обращении к API MAX."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Сохраняет сообщение и HTTP-статус ответа MAX."""

        super().__init__(message)
        self.status_code = status_code


class MAXClient:
    """Асинхронный клиент для работы с API MAX."""

    def __init__(
        self,
        *,
        access_token: str,
        chat_id: int | None = None,
        api_url: str = "https://platform-api2.max.ru",
        ca_file: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Создаёт клиент MAX с настройками канала и TLS."""

        self._access_token = access_token
        self._chat_id = chat_id
        self._api_url = api_url.rstrip("/")
        self._ca_file = ca_file
        self._http_client = http_client

    async def get_updates(
        self,
        *,
        limit: int = 100,
        timeout: int = 0,
        marker: int | None = None,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Возвращает события бота через тестовый Long Polling MAX."""

        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        if types:
            params["types"] = ",".join(types)
        return await self._get_json("/updates", params=params)

    async def get_subscriptions(self) -> dict[str, Any]:
        """Возвращает активные webhook-подписки бота MAX."""

        return await self._get_json("/subscriptions")

    async def create_subscription(
        self,
        *,
        url: str,
        secret: str,
        update_types: list[str],
    ) -> dict[str, Any]:
        """Создаёт webhook-подписку MAX."""

        return await self._post_json(
            "/subscriptions",
            body={"url": url, "secret": secret, "update_types": update_types},
        )

    async def get_chat(self, chat_id: int) -> dict[str, Any]:
        """Возвращает информацию о конкретном чате или канале MAX."""

        return await self._get_json(f"/chats/{chat_id}")

    async def publish_post(
        self,
        *,
        text: str,
        image_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Публикует текст и фотографии по внешним URL в настроенный канал."""

        if self._chat_id is None:
            raise ValueError("Для публикации необходимо указать chat_id")

        clean_text = text.strip()
        images = image_urls or []
        if not clean_text and not images:
            raise ValueError("Нельзя опубликовать пустой пост")
        if len(clean_text) > 4000:
            raise ValueError("Текст поста превышает лимит MAX в 4000 символов")

        body: dict[str, Any] = {"text": clean_text or None}
        if images:
            body["attachments"] = [
                {"type": "image", "payload": {"url": url}} for url in images
            ]

        if self._http_client is not None:
            return await self._send(self._http_client, body)

        async with httpx.AsyncClient(timeout=30.0, verify=self._ssl_context()) as client:
            return await self._send(client, body)

    def _ssl_context(self) -> ssl.SSLContext:
        """Создаёт SSL-контекст с дополнительным CA MAX при необходимости."""

        ssl_context = ssl.create_default_context()
        if self._ca_file:
            ssl_context.load_verify_locations(cafile=self._ca_file)
        return ssl_context

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполняет авторизованный GET-запрос к MAX и возвращает JSON-объект."""

        if self._http_client is not None:
            return await self._request_get(self._http_client, path, params=params)

        async with httpx.AsyncClient(timeout=95.0, verify=self._ssl_context()) as client:
            return await self._request_get(client, path, params=params)

    async def _post_json(self, path: str, *, body: dict[str, Any]) -> dict[str, Any]:
        """Выполняет авторизованный POST-запрос к MAX и возвращает JSON-объект."""

        if self._http_client is not None:
            return await self._request_post(self._http_client, path, body=body)

        async with httpx.AsyncClient(timeout=30.0, verify=self._ssl_context()) as client:
            return await self._request_post(client, path, body=body)

    async def _request_get(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Отправляет GET-запрос к MAX."""

        try:
            response = await client.get(
                f"{self._api_url}{path}",
                params=params,
                headers={"Authorization": self._access_token},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise MAXAPIError(detail, exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise MAXAPIError(f"Не удалось выполнить запрос к MAX: {exc}") from exc

        return self._decode_dict(response)

    async def _request_post(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Отправляет POST-запрос к MAX."""

        try:
            response = await client.post(
                f"{self._api_url}{path}",
                headers={"Authorization": self._access_token},
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise MAXAPIError(detail, exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise MAXAPIError(f"Не удалось выполнить запрос к MAX: {exc}") from exc

        return self._decode_dict(response)

    @staticmethod
    def _decode_dict(response: httpx.Response) -> dict[str, Any]:
        """Проверяет, что MAX вернул JSON-объект."""

        try:
            result = response.json()
        except ValueError as exc:
            raise MAXAPIError("MAX вернул ответ не в формате JSON") from exc

        if not isinstance(result, dict):
            raise MAXAPIError("MAX вернул неожиданный формат ответа")
        return result

    async def _send(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Отправляет подготовленное тело запроса в API MAX."""

        try:
            response = await client.post(
                f"{self._api_url}/messages",
                params={"chat_id": self._chat_id},
                headers={"Authorization": self._access_token},
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise MAXAPIError(detail, exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise MAXAPIError(f"Не удалось выполнить запрос к MAX: {exc}") from exc

        return self._decode_dict(response)
