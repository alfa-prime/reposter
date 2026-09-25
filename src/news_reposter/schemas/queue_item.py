import base64
import binascii
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from news_reposter.db.models.enums import (
    PublicationAttemptStatus,
    PublicationStatus,
    QueueItemStatus,
)
from news_reposter.services.media_validation import (
    MediaValidationError,
    validate_image_content,
)


class QueueItemCreate(BaseModel):
    post_id: int = Field(gt=0, description="Идентификатор исходного поста")
    target_id: int = Field(gt=0, description="Идентификатор целевого канала")
    rewritten_text: str | None = Field(
        default=None, description="Подготовленный текст поста, если он уже известен"
    )


class QueueItemUpdate(BaseModel):
    rewritten_text: str | None = Field(
        default=None,
        description="Отредактированный текст публикации; null очищает значение",
    )
    signature_text: str | None = Field(
        default=None,
        max_length=4000,
        description="Подпись конкретной публикации; null означает использовать подпись канала",
    )

    @model_validator(mode="after")
    def validate_changes(self) -> "QueueItemUpdate":
        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        return self


class QueueItemSchedule(BaseModel):
    scheduled_at: datetime = Field(
        description="Дата и время публикации с часовым поясом"
    )

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("дата и время публикации должны содержать часовой пояс")
        if value <= datetime.now(UTC):
            raise ValueError("дата и время публикации должны быть в будущем")
        return value


class QueueMediaUpload(BaseModel):
    filename: str = Field(
        min_length=1, max_length=255, description="Исходное имя файла"
    )
    content_type: str = Field(description="MIME-тип изображения")
    data_base64: str = Field(min_length=1, description="Содержимое файла в Base64")

    @model_validator(mode="after")
    def validate_real_image_type(self) -> "QueueMediaUpload":
        try:
            content = base64.b64decode(self.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("некорректные Base64-данные изображения") from exc
        if not content:
            raise ValueError("пустой файл изображения")
        try:
            validate_image_content(content, self.content_type)
        except MediaValidationError as exc:
            raise ValueError(str(exc)) from exc
        return self


class QueuePhotoRead(BaseModel):
    attachment_id: int = Field(description="Идентификатор вложения")
    external_attachment_id: str | None = Field(
        default=None, description="Идентификатор фотографии во внешнем источнике"
    )
    source_url: str = Field(description="URL фотографии")
    position: int = Field(description="Позиция фотографии в публикации")
    kind: str = Field(
        default="source", description="Источник фото: source или uploaded"
    )
    media_id: str | None = Field(
        default=None, description="Идентификатор загруженного редактором файла"
    )


class PublicationAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    publication_attempt_id: int
    attempt_number: int
    status: PublicationAttemptStatus
    trigger: str
    external_message_id: str | None = None
    publication_url: str | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    check_count: int = 0
    last_checked_at: datetime | None = None


class PublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: PublicationStatus
    external_message_id: str | None = None
    publication_url: str | None = None
    attempts: int
    error_message: str | None = None
    published_at: datetime | None = None
    attempt_history: list[PublicationAttemptRead] = Field(default_factory=list)


class QueueItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queue_item_id: int
    post_id: int
    target_id: int
    rewritten_text: str | None
    signature_text: str | None = None
    status: QueueItemStatus
    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    error_message: str | None
    original_text: str | None = None
    source_url: str | None = None
    source_published_at: datetime | None = None
    photos: list[QueuePhotoRead] = Field(default_factory=list)
    target_name: str | None = None
    target_platform: str | None = None
    target_url: str | None = None
    target_default_signature: str | None = None
    publication: PublicationRead | None = None


class PublicationRecoveryResult(BaseModel):
    item: QueueItemRead
    outcome: str
    message: str


class MarkPublishedRequest(BaseModel):
    publication_url: str | None = Field(default=None, max_length=2048)
    external_message_id: str | None = Field(default=None, max_length=255)
    comment: str = Field(min_length=3, max_length=1000)


class RetryPublicationRequest(BaseModel):
    checked_channel: bool
    accept_duplicate_risk: bool


class QueuePageRead(BaseModel):
    """Одна страница редакционной очереди и счётчики её статусов."""

    items: list[QueueItemRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    status_counts: dict[str, int]
