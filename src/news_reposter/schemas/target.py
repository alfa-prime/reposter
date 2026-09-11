from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TargetBase(BaseModel):
    """Общие поля цели публикации."""

    name: str = Field(min_length=1, max_length=200, description="Понятное название канала или чата", examples=["Новости 51 региона"])
    platform: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$", description="Код платформы в нижнем регистре", examples=["max"])
    external_id: str = Field(min_length=1, max_length=255, description="Идентификатор канала или чата во внешней платформе", examples=["-77162942582085"])
    url: str | None = Field(default=None, max_length=2048, description="Необязательная ссылка на канал или чат", examples=["https://max.ru/channel_51_news"])
    default_signature: str | None = Field(default=None, max_length=4000, description="Подпись, автоматически подставляемая к новым публикациям канала")
    is_active: bool = Field(default=True, description="Можно ли публиковать посты в эту цель")

    @field_validator("name", "external_id", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url должен быть абсолютной HTTP-ссылкой")
        return value


class TargetCreate(TargetBase):
    """Данные для создания цели публикации."""
    model_config = ConfigDict(json_schema_extra={"example": {"name": "Новости 51 региона", "platform": "max", "external_id": "-77162942582085", "url": "https://max.ru/channel_51_news", "default_signature": "📣 Подписывайтесь на наш канал", "is_active": True}})


class TargetUpdate(BaseModel):
    """Поля цели публикации, которые можно изменить."""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="Новое название цели")
    platform: str | None = Field(default=None, min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$", description="Новый код платформы")
    external_id: str | None = Field(default=None, min_length=1, max_length=255, description="Новый ID канала или чата во внешней платформе")
    url: str | None = Field(default=None, max_length=2048, description="Новая ссылка; значение null удаляет текущую ссылку")
    default_signature: str | None = Field(default=None, max_length=4000, description="Подпись канала; null очищает подпись по умолчанию")
    is_active: bool | None = Field(default=None, description="Включить или приостановить публикацию")

    @field_validator("name", "external_id", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url должен быть абсолютной HTTP-ссылкой")
        return value

    @model_validator(mode="after")
    def validate_changes(self) -> "TargetUpdate":
        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        required_fields = self.model_fields_set - {"url", "default_signature"}
        if any(getattr(self, field) is None for field in required_fields):
            raise ValueError("обязательные поля цели не могут быть null")
        return self


class TargetRead(TargetBase):
    """Цель публикации в ответе API."""

    model_config = ConfigDict(from_attributes=True)
    target_id: int = Field(description="Идентификатор цели в нашей базе")
    created_at: datetime = Field(description="Дата и время создания записи")
    updated_at: datetime = Field(description="Дата и время последнего изменения")
