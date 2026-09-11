from enum import StrEnum


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Возвращает строковые значения для хранения enum в базе."""

    return [item.value for item in enum_class]


class PostStatus(StrEnum):
    """Состояние приёма и первичной обработки исходного поста."""

    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


class QueueItemStatus(StrEnum):
    """Редакционный статус поста для конкретной цели публикации."""

    PENDING = "pending"
    REWRITING = "rewriting"
    AWAITING_MODERATION = "awaiting_moderation"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    FAILED = "failed"


class AttachmentType(StrEnum):
    """Тип вложения исходного поста."""

    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LINK = "link"
    OTHER = "other"


class PublicationStatus(StrEnum):
    """Состояние отправки подготовленного поста во внешнюю платформу."""

    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
