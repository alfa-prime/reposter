from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SOURCE_HOST_PLATFORMS = {
    "vk.com": "vk",
    "vk.ru": "vk",
    "t.me": "telegram",
    "telegram.me": "telegram",
    "max.ru": "max",
}


def source_platform_from_url(value: str) -> str:
    """Определяет поддерживаемую платформу по ссылке на источник."""

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url должен быть абсолютной HTTP-ссылкой")

    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    platform = SOURCE_HOST_PLATFORMS.get(host)
    if platform is None:
        raise ValueError("поддерживаются ссылки источников VK, Telegram и MAX")
    if not parsed.path.strip("/"):
        raise ValueError(
            "ссылка должна вести на конкретный источник, а не на главную страницу"
        )
    return platform


class SourceBase(BaseModel):
    """Общие поля источника."""

    name: str = Field(
        min_length=1, max_length=200, description="Понятное название источника"
    )
    platform: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[a-z][a-z0-9_-]+$",
        description="Код платформы",
    )
    url: str = Field(
        min_length=1,
        max_length=2048,
        description="Полная ссылка на источник публикаций",
    )
    icon_url: str | None = Field(
        default=None, max_length=2048, description="Аватар источника"
    )
    is_active: bool = Field(
        default=True, description="Нужно ли получать новые посты из этого источника"
    )

    @field_validator("name", "url", "icon_url", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        source_platform_from_url(value)
        return value

    @model_validator(mode="after")
    def validate_platform_matches_url(self) -> "SourceBase":
        detected = source_platform_from_url(self.url)
        if self.platform != detected:
            raise ValueError(f"для этой ссылки платформа должна быть {detected}")
        return self


class SourceCreate(SourceBase):
    """Данные для создания источника."""


class SourceUpdate(BaseModel):
    """Поля источника, которые можно изменить."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    platform: str | None = Field(
        default=None, min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$"
    )
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    icon_url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None

    @field_validator("name", "url", "icon_url", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        source_platform_from_url(value)
        return value

    @model_validator(mode="after")
    def validate_changes(self) -> "SourceUpdate":
        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set
            if field != "icon_url"
        ):
            raise ValueError("поля источника не могут быть null")
        if "url" in self.model_fields_set and "platform" in self.model_fields_set:
            assert self.url is not None
            assert self.platform is not None
            detected = source_platform_from_url(self.url)
            if self.platform != detected:
                raise ValueError(f"для этой ссылки платформа должна быть {detected}")
        return self


class SourceRead(SourceBase):
    """Источник в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    source_id: int
    created_at: datetime
    updated_at: datetime
