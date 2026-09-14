import asyncio
import ssl
import time
from typing import Any
from uuid import uuid4

import httpx

from .base import LLMProviderError, RewriteRequest, RewriteResult


class GigaChatProvider:
    """Провайдер GigaChat через официальный REST API."""

    name = "gigachat"

    def __init__(
        self,
        *,
        credentials: str,
        scope: str,
        model: str,
        api_url: str,
        auth_url: str,
        ca_file: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not credentials.strip():
            raise ValueError("Не задан ключ авторизации GigaChat")

        self.credentials = credentials.strip()
        self.scope = scope
        self.model = model
        self.api_url = api_url.rstrip("/")
        self.auth_url = auth_url
        self.timeout = timeout
        self._transport = transport
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

        if ca_file:
            self._verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=ca_file)
        else:
            self._verify = True

    async def rewrite(self, request: RewriteRequest) -> RewriteResult:
        text = request.text.strip()
        if not text:
            raise LLMProviderError("Нечего переписывать: исходный текст пуст")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt.strip()},
                {"role": "user", "content": text},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

        data = await self._request_completion(payload)
        try:
            result_text = str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("GigaChat вернул ответ в неожиданном формате") from exc

        if not result_text:
            raise LLMProviderError("GigaChat вернул пустой текст")

        raw_usage = data.get("usage") or {}
        usage = {
            key: value
            for key, value in raw_usage.items()
            if isinstance(key, str) and isinstance(value, int)
        }
        return RewriteResult(
            text=result_text,
            provider=self.name,
            model=str(data.get("model") or self.model),
            usage=usage,
        )

    async def _request_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = await self._get_access_token()
        response = await self._post_completion(payload, token)

        if response.status_code == 401:
            self._access_token = None
            self._access_token_expires_at = 0.0
            token = await self._get_access_token()
            response = await self._post_completion(payload, token)

        if response.is_error:
            raise self._http_error("GigaChat не выполнил запрос", response)

        try:
            body = response.json()
        except ValueError as exc:
            raise LLMProviderError("GigaChat вернул некорректный JSON") from exc
        if not isinstance(body, dict):
            raise LLMProviderError("GigaChat вернул ответ в неожиданном формате")
        return body

    async def _post_completion(self, payload: dict[str, Any], token: str) -> httpx.Response:
        async with self._client() as client:
            return await client.post(
                f"{self.api_url}/chat/completions",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json=payload,
            )

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._access_token_expires_at - 30:
            return self._access_token

        async with self._token_lock:
            now = time.time()
            if self._access_token and now < self._access_token_expires_at - 30:
                return self._access_token

            async with self._client() as client:
                response = await client.post(
                    self.auth_url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Basic {self.credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "RqUID": str(uuid4()),
                    },
                    data={"scope": self.scope},
                )

            if response.is_error:
                raise self._http_error("Не удалось получить токен GigaChat", response)

            try:
                body = response.json()
                token = str(body["access_token"])
                expires_at = float(body["expires_at"])
            except (ValueError, KeyError, TypeError) as exc:
                raise LLMProviderError("GigaChat вернул некорректный ответ авторизации") from exc

            # API исторически возвращал expires_at как в секундах, так и в миллисекундах.
            if expires_at > 10_000_000_000:
                expires_at /= 1000

            self._access_token = token
            self._access_token_expires_at = expires_at
            return token

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            verify=self._verify,
            timeout=self.timeout,
            transport=self._transport,
        )

    @staticmethod
    def _http_error(prefix: str, response: httpx.Response) -> LLMProviderError:
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = str(body.get("message") or body.get("detail") or body.get("error") or "")
        except ValueError:
            pass
        suffix = f": {detail}" if detail else ""
        return LLMProviderError(f"{prefix} ({response.status_code}){suffix}")
