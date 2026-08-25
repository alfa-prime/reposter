from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class VKPost(BaseModel):
    """Поля поста, которые понадобятся для рерайта и публикации в MAX."""

    model_config = ConfigDict(extra="allow")

    id: int
    owner_id: int
    from_id: int | None = None
    date: int
    text: str = ""
    post_type: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    is_pinned: int | None = None

    @computed_field
    @property
    def source_url(self) -> str:
        """Возвращает прямую ссылку на исходный пост."""

        return f"https://vk.com/wall{self.owner_id}_{self.id}"

    @computed_field
    @property
    def published_at(self) -> datetime:
        """Возвращает время публикации в UTC."""

        return datetime.fromtimestamp(self.date, tz=timezone.utc)


class VKWallResponse(BaseModel):
    """Полезная часть успешного ответа метода wall.get."""

    count: int
    items: list[VKPost]


class VKWallEnvelope(BaseModel):
    """Обёртка ответа VK с результатом или описанием ошибки."""

    response: VKWallResponse | None = None
    error: dict[str, Any] | None = None
