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
    """Асинхронный клиент для публикации сообщений и изображений в MAX."""

    def __init__(
        self,
        *,
        access_token: str,
        chat_id: int,
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

    async def publish_post(
        self,
        *,
        text: str,
        image_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Публикует текст и фотографии по внешним URL в настроенный канал."""

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

        ssl_context = ssl.create_default_context()
        if self._ca_file:
            ssl_context.load_verify_locations(cafile=self._ca_file)

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=ssl_context,
        ) as client:
            return await self._send(client, body)

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

        try:
            result = response.json()
        except ValueError as exc:
            raise MAXAPIError("MAX вернул ответ не в формате JSON") from exc

        if not isinstance(result, dict):
            raise MAXAPIError("MAX вернул неожиданный формат ответа")
        return result
