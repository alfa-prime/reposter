from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class VKPost(BaseModel):
    """Fields needed for later rewriting and publication in MAX."""

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
        return f"https://vk.com/wall{self.owner_id}_{self.id}"

    @computed_field
    @property
    def published_at(self) -> datetime:
        return datetime.fromtimestamp(self.date, tz=timezone.utc)


class VKWallResponse(BaseModel):
    count: int
    items: list[VKPost]


class VKWallEnvelope(BaseModel):
    response: VKWallResponse | None = None
    error: dict[str, Any] | None = None

