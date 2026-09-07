from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TargetBase(BaseModel):
    """Общие поля цели публикации."""

    name: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$")
    external_id: str = Field(min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    is_active: bool = True

    @field_validator("name", "external_id", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """Убирает случайные пробелы по краям текстовых полей."""

        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        """Приводит название платформы к единому виду."""

        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> object:
        """Проверяет необязательную ссылку на канал или чат."""

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


class TargetUpdate(BaseModel):
    """Поля цели публикации, которые можно изменить."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    platform: str | None = Field(
        default=None,
        min_length=2,
        max_length=32,
        pattern=r"^[a-z][a-z0-9_-]+$",
    )
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None

    @field_validator("name", "external_id", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """Убирает пробелы по краям изменяемых текстовых полей."""

        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        """Приводит изменённую платформу к нижнему регистру."""

        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> object:
        """Проверяет изменённую ссылку и разрешает удалить её через null."""

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
        """Проверяет, что запрос содержит допустимые изменения."""

        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        required_fields = self.model_fields_set - {"url"}
        if any(getattr(self, field) is None for field in required_fields):
            raise ValueError("обязательные поля цели не могут быть null")
        return self


class TargetRead(TargetBase):
    """Цель публикации в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    target_id: int
    created_at: datetime
    updated_at: datetime
