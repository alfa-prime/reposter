from enum import StrEnum


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Возвращает строковые значения для хранения enum в базе."""

    return [item.value for item in enum_class]


class PostStatus(StrEnum):
    """Этап обработки полученного поста."""

    RECEIVED = "received"
    REWRITING = "rewriting"
    REWRITTEN = "rewritten"
    AWAITING_MODERATION = "awaiting_moderation"
    APPROVED = "approved"
    REJECTED = "rejected"
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
    """Состояние отправки поста в одну цель публикации."""

    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
