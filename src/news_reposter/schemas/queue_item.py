from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from news_reposter.db.models.enums import QueueItemStatus


class QueueItemCreate(BaseModel):
    """Данные для помещения исходного поста в очередь целевого канала."""

    post_id: int = Field(gt=0, description="Идентификатор исходного поста")
    target_id: int = Field(gt=0, description="Идентификатор целевого канала")
    rewritten_text: str | None = Field(
        default=None,
        description="Подготовленный текст поста, если он уже известен",
    )


class QueueItemUpdate(BaseModel):
    """Редактируемые поля элемента очереди без прямой смены статуса."""

    rewritten_text: str | None = Field(
        default=None,
        description="Отредактированный текст публикации; null очищает значение",
    )

    @model_validator(mode="after")
    def validate_changes(self) -> "QueueItemUpdate":
        if not self.model_fields_set:
            raise ValueError("нужно передать хотя бы одно поле")
        return self


class QueueItemSchedule(BaseModel):
    """Дата и время планируемой публикации."""

    scheduled_at: datetime = Field(
        description="Дата и время публикации с часовым поясом"
    )


class QueueMediaUpload(BaseModel):
    """Пользовательское изображение, добавляемое редактором к публикации."""

    filename: str = Field(min_length=1, max_length=255, description="Исходное имя файла")
    content_type: str = Field(description="MIME-тип изображения")
    data_base64: str = Field(min_length=1, description="Содержимое файла в Base64")


class QueuePhotoRead(BaseModel):
    """Фотография публикации для отображения в редакционной очереди."""

    attachment_id: int = Field(description="Идентификатор вложения")
    external_attachment_id: str | None = Field(
        default=None,
        description="Идентификатор фотографии во внешнем источнике",
    )
    source_url: str = Field(description="URL фотографии")
    position: int = Field(description="Позиция фотографии в публикации")
    kind: str = Field(default="source", description="Источник фото: source или uploaded")
    media_id: str | None = Field(
        default=None,
        description="Идентификатор загруженного редактором файла",
    )


class QueueItemRead(BaseModel):
    """Элемент редакционной очереди в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    queue_item_id: int = Field(description="Идентификатор элемента очереди")
    post_id: int = Field(description="Идентификатор исходного поста")
    target_id: int = Field(description="Идентификатор целевого канала")
    rewritten_text: str | None = Field(description="Подготовленный текст")
    status: QueueItemStatus = Field(description="Редакционный статус")
    scheduled_at: datetime | None = Field(description="Запланированное время публикации")
    created_at: datetime = Field(description="Дата создания элемента очереди")
    updated_at: datetime = Field(description="Дата последнего изменения")
    error_message: str | None = Field(description="Ошибка редакционной обработки")

    original_text: str | None = Field(
        default=None,
        description="Исходный текст поста из источника",
    )
    source_url: str | None = Field(
        default=None,
        description="Ссылка на исходный пост",
    )
    source_published_at: datetime | None = Field(
        default=None,
        description="Дата публикации исходного поста",
    )
    photos: list[QueuePhotoRead] = Field(
        default_factory=list,
        description="Фотографии исходного поста и добавленные редактором изображения",
    )
    target_name: str | None = Field(
        default=None,
        description="Название целевого канала",
    )
    target_platform: str | None = Field(
        default=None,
        description="Платформа целевого канала",
    )
    target_url: str | None = Field(
        default=None,
        description="Ссылка на целевой канал",
    )
