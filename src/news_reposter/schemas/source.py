from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceBase(BaseModel):
    """Общие поля источника."""

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Понятное название источника",
        examples=["Полуостров 51"],
    )
    platform: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[a-z][a-z0-9_-]+$",
        description="Код платформы в нижнем регистре",
        examples=["vk"],
    )
    url: str = Field(
        min_length=1,
        max_length=2048,
        description="Полная ссылка на источник публикаций",
        examples=["https://vk.ru/peninsula51"],
    )
    is_active: bool = Field(
        default=True,
        description="Нужно ли получать новые посты из этого источника",
    )

    @field_validator("name", "url", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """Убирает случайные пробелы по краям текстовых полей."""

        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        """Приводит название платформы к единому виду."""

        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Разрешает только абсолютные HTTP-ссылки на источник."""

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url должен быть абсолютной HTTP-ссылкой")
        return value


class SourceCreate(SourceBase):
    """Данные для создания источника."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Полуостров 51",
                "platform": "vk",
                "url": "https://vk.ru/peninsula51",
                "is_active": True,
            }
        }
    )


class SourceUpdate(BaseModel):
    """Поля источника, которые можно изменить."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Новое название источника",
    )
    platform: str | None = Field(
        default=None,
        min_length=2,
        max_length=32,
        pattern=r"^[a-z][a-z0-9_-]+$",
        description="Новый код платформы",
    )
    url: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Новая полная ссылка на источник",
    )
    is_active: bool | None = Field(
        default=None,
        description="Включить или приостановить получение постов",
    )

    @field_validator("name", "url", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """Убирает пробелы по краям изменяемых текстовых полей."""

        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        """Приводит изменённое название платформы к нижнему регистру."""

        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        """Проверяет изменённую ссылку на источник."""

        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url должен быть абсолютной HTTP-ссылкой")
        return value

    @model_validator(mode="after")
    def validate_changes(self) -> "SourceUpdate":
        """Не допускает пустой запрос на изменение источника."""

        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("поля источника не могут быть null")
        return self


class SourceRead(SourceBase):
    """Источник в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    source_id: int = Field(description="Идентификатор источника в нашей базе")
    created_at: datetime = Field(description="Дата и время создания записи")
    updated_at: datetime = Field(description="Дата и время последнего изменения")
