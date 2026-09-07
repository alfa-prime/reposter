from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from news_reposter.config import get_settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="APIKeyHeader",
    description="API-ключ сервиса из переменной окружения `API_KEY`.",
    auto_error=False,
)

API_KEY_RESPONSES = {
    401: {"description": "Неверный или отсутствующий API-ключ"},
}


async def require_api_key(
    provided_api_key: Annotated[str | None, Security(api_key_header)],
) -> None:
    """Проверяет API-ключ из заголовка запроса."""

    expected_api_key = get_settings().api_key
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_KEY не настроен",
        )

    if provided_api_key is None or not compare_digest(
        provided_api_key,
        expected_api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или отсутствующий API-ключ",
            headers={"WWW-Authenticate": "ApiKey"},
        )


ApiKeyDep = Annotated[None, Depends(require_api_key)]
