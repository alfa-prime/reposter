from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MAXPublishResponse(BaseModel):
    """Результат публикации поста VK в канал MAX."""

    model_config = ConfigDict(extra="allow")

    source_url: str = Field(
        description="Ссылка на исходный пост VK",
        examples=["https://vk.com/wall-185052131_213307"],
    )
    photo_count: int = Field(
        ge=0,
        description="Количество переданных в MAX фотографий",
    )
    message: dict[str, Any] = Field(
        description="Созданное сообщение из ответа MAX API"
    )
