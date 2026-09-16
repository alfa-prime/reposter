from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from news_reposter.db.models import (
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionSourceRunStatus,
)


class CollectionSettingsData(BaseModel):
    enabled: bool = Field(description="Включён ли автоматический сбор")
    interval_minutes: int = Field(ge=1, le=1440)
    start_time: time
    end_time: time
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("неизвестный часовой пояс") from exc
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "CollectionSettingsData":
        if self.start_time == self.end_time:
            raise ValueError("начало и конец рабочего окна не должны совпадать")
        return self


class CollectionSettingsRead(CollectionSettingsData):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime


class CollectionSettingsUpdate(CollectionSettingsData):
    """Полный снимок редактируемых настроек расписания."""


class CollectionSourceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collection_source_run_id: int
    source_id: int | None
    source_name: str
    source_url: str
    status: CollectionSourceRunStatus
    started_at: datetime
    finished_at: datetime | None
    last_post_id_before: str | None
    last_post_id_after: str | None
    posts_found: int
    posts_created: int
    queue_items_created: int
    error_type: str | None
    error_message: str | None


class CollectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collection_run_id: int
    trigger: CollectionRunTrigger
    status: CollectionRunStatus
    started_at: datetime
    finished_at: datetime | None
    sources_total: int
    sources_checked: int
    sources_succeeded: int
    sources_failed: int
    posts_found: int
    posts_created: int
    queue_items_created: int
    error_message: str | None


class CollectionRunDetail(CollectionRunRead):
    source_runs: list[CollectionSourceRunRead]


class CollectionRunPage(BaseModel):
    items: list[CollectionRunRead]
    total: int
    offset: int
    limit: int


class CollectionStatusRead(BaseModel):
    enabled: bool
    running: bool
    next_run_at: datetime | None
    last_run: CollectionRunRead | None
    last_success_at: datetime | None
    consecutive_failures: int
