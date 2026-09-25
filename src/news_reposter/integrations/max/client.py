from typing import Any, Literal

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
        http_client: httpx.AsyncClient,
        chat_id: int | None = None,
        api_url: str = "https://platform-api2.max.ru",
    ) -> None:
        self._access_token = access_token
        self._chat_id = chat_id
        self._api_url = api_url.rstrip("/")
        self._http_client = http_client

    async def get_updates(
        self,
        *,
        limit: int = 100,
        timeout: int = 0,
        marker: int | None = None,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        if types:
            params["types"] = ",".join(types)
        return await self._get_json("/updates", params=params)

    async def get_subscriptions(self) -> dict[str, Any]:
        return await self._get_json("/subscriptions")

    async def create_subscription(
        self,
        *,
        url: str,
        secret: str,
        update_types: list[str],
    ) -> dict[str, Any]:
        return await self._post_json(
            "/subscriptions",
            body={"url": url, "secret": secret, "update_types": update_types},
        )

    async def get_chat(self, chat_id: int) -> dict[str, Any]:
        return await self._get_json(f"/chats/{chat_id}")

    async def get_messages(
        self,
        *,
        chat_id: int | None = None,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
        count: int = 100,
    ) -> dict[str, Any]:
        """Возвращает сообщения канала для сверки неопределённой публикации."""

        effective_chat_id = chat_id if chat_id is not None else self._chat_id
        if effective_chat_id is None:
            raise ValueError("Для чтения сообщений необходимо указать chat_id")
        params: dict[str, Any] = {"chat_id": effective_chat_id, "count": count}
        if from_timestamp is not None:
            params["from"] = from_timestamp
        if to_timestamp is not None:
            params["to"] = to_timestamp
        return await self._get_json("/messages", params=params)

    async def request_upload(
        self,
        media_type: Literal["image", "video", "audio", "file"],
    ) -> dict[str, Any]:
        """Получает у MAX одноразовый URL для загрузки медиа."""

        return await self._post_json("/uploads", body=None, params={"type": media_type})

    async def upload_media(
        self,
        *,
        media_type: Literal["image", "video"],
        filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Загружает один файл в MAX и возвращает token вложения."""

        upload = await self.request_upload(media_type)
        upload_url = upload.get("url")
        if not isinstance(upload_url, str) or not upload_url:
            raise MAXAPIError("MAX не вернул URL для загрузки медиа")

        initial_token = upload.get("token")
        try:
            result = await self._upload_to_url(
                upload_url,
                filename,
                content,
                content_type,
            )
        except MAXAPIError as exc:
            # Для видео MAX выдаёт token ещё на шаге POST /uploads. Некоторые
            # upload-хосты при успешной загрузке отвечают пустым телом или не-JSON.
            # В этом случае HTTP-загрузка уже успешна, и можно использовать token
            # из первого ответа. HTTP-ошибки загрузки по-прежнему пробрасываем.
            non_json_upload_response = str(exc) in {
                "MAX вернул ответ не в формате JSON",
                "MAX вернул неожиданный формат ответа",
            }
            if not (
                isinstance(initial_token, str)
                and initial_token
                and non_json_upload_response
            ):
                raise
            result = {}

        token = result.get("token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            token = initial_token if isinstance(initial_token, str) else None
        if not token:
            retval = result.get("retval") if isinstance(result, dict) else None
            if isinstance(retval, dict):
                nested = retval.get("token")
                token = nested if isinstance(nested, str) else None
        if not token:
            raise MAXAPIError("MAX не вернул token загруженного медиа")
        return token

    async def publish_post(
        self,
        *,
        text: str,
        image_urls: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        text_format: Literal["markdown", "html"] | None = "markdown",
    ) -> dict[str, Any]:
        """Публикует подготовленный пост в настроенный канал MAX."""

        if self._chat_id is None:
            raise ValueError("Для публикации необходимо указать chat_id")

        clean_text = text.strip()
        all_attachments = list(attachments or [])
        for url in image_urls or []:
            all_attachments.append({"type": "image", "payload": {"url": url}})

        if not clean_text and not all_attachments:
            raise ValueError("Нельзя опубликовать пустой пост")
        if len(clean_text) > 4000:
            raise ValueError("Текст поста превышает лимит MAX в 4000 символов")
        if len(all_attachments) > 12:
            raise ValueError("MAX позволяет прикрепить не более 12 медиафайлов")

        body: dict[str, Any] = {"text": clean_text or None}
        if all_attachments:
            body["attachments"] = all_attachments
        if clean_text and text_format:
            body["format"] = text_format

        return await self._send(body)

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request_get(path, params=params)

    async def _post_json(
        self,
        path: str,
        *,
        body: dict[str, Any] | None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request_post(path, body=body, params=params)

    async def _request_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.get(
                f"{self._api_url}{path}",
                params=params,
                headers={"Authorization": self._access_token},
                timeout=95.0,
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
        path: str,
        *,
        body: dict[str, Any] | None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.post(
                f"{self._api_url}{path}",
                params=params,
                headers={"Authorization": self._access_token},
                json=body,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise MAXAPIError(detail, exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise MAXAPIError(f"Не удалось выполнить запрос к MAX: {exc}") from exc

        return self._decode_dict(response)

    async def _upload_to_url(
        self,
        url: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.post(
                url,
                files={"data": (filename, content, content_type)},
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise MAXAPIError(
                f"Ошибка загрузки медиа в MAX: {detail}",
                exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise MAXAPIError(f"Не удалось загрузить медиа в MAX: {exc}") from exc
        return self._decode_dict(response)

    @staticmethod
    def _decode_dict(response: httpx.Response) -> dict[str, Any]:
        try:
            result = response.json()
        except ValueError as exc:
            raise MAXAPIError("MAX вернул ответ не в формате JSON") from exc

        if not isinstance(result, dict):
            raise MAXAPIError("MAX вернул неожиданный формат ответа")
        return result

    async def _send(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.post(
                f"{self._api_url}/messages",
                params={"chat_id": self._chat_id},
                headers={"Authorization": self._access_token},
                json=body,
                timeout=60.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise MAXAPIError(detail, exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise MAXAPIError(f"Не удалось выполнить запрос к MAX: {exc}") from exc

        return self._decode_dict(response)
