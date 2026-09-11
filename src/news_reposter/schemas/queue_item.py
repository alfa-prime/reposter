from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from news_reposter.db.models.enums import QueueItemStatus


class QueueItemCreate(BaseModel):
    post_id: int = Field(gt=0, description="Идентификатор исходного поста")
    target_id: int = Field(gt=0, description="Идентификатор целевого канала")
    rewritten_text: str | None = Field(default=None, description="Подготовленный текст поста, если он уже известен")


class QueueItemUpdate(BaseModel):
    rewritten_text: str | None = Field(default=None, description="Отредактированный текст публикации; null очищает значение")
    signature_text: str | None = Field(default=None, max_length=4000, description="Подпись конкретной публикации; null означает использовать подпись канала")

    @model_validator(mode="after")
    def validate_changes(self) -> "QueueItemUpdate":
        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        return self


class QueueItemSchedule(BaseModel):
    scheduled_at: datetime = Field(description="Дата и время публикации с часовым поясом")


class QueueMediaUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255, description="Исходное имя файла")
    content_type: str = Field(description="MIME-тип изображения")
    data_base64: str = Field(min_length=1, description="Содержимое файла в Base64")


class QueuePhotoRead(BaseModel):
    attachment_id: int = Field(description="Идентификатор вложения")
    external_attachment_id: str | None = Field(default=None, description="Идентификатор фотографии во внешнем источнике")
    source_url: str = Field(description="URL фотографии")
    position: int = Field(description="Позиция фотографии в публикации")
    kind: str = Field(default="source", description="Источник фото: source или uploaded")
    media_id: str | None = Field(default=None, description="Идентификатор загруженного редактором файла")


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
