from __future__ import annotations


class MediaValidationError(ValueError):
    """Файл не соответствует заявленному или поддерживаемому формату."""


def detect_image_type(content: bytes) -> str | None:
    """Определяет поддерживаемый тип изображения по сигнатуре файла."""

    if len(content) >= 3 and content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(content) >= 8 and content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if (
        len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    return None


def detect_video_type(content: bytes) -> str | None:
    """Определяет MP4/MOV/WebM по заголовку контейнера.

    Это не декодирование всего ролика, но проверка уже основана на фактических
    байтах файла, а не на MIME-типе, который сообщил браузер.
    """

    # WebM использует контейнер EBML. В заголовке DocType должен быть webm.
    if len(content) >= 4 and content[:4] == b"\x1aE\xdf\xa3":
        header = content[:4096].lower()
        if b"webm" in header:
            return "video/webm"

    # MP4 и QuickTime MOV основаны на ISO Base Media File Format и содержат
    # box `ftyp` в начале файла. Major brand qt означает QuickTime.
    if len(content) >= 12 and content[4:8] == b"ftyp":
        brand = content[8:12].lower()
        if brand.startswith(b"qt"):
            return "video/quicktime"
        return "video/mp4"

    return None


def validate_image_content(content: bytes, declared_type: str) -> str:
    """Проверяет, что изображение реально соответствует заявленному MIME."""

    detected = detect_image_type(content)
    if detected is None:
        raise MediaValidationError(
            "Содержимое файла не похоже на JPEG, PNG или WebP"
        )
    if detected != declared_type.lower():
        raise MediaValidationError(
            f"Фактический тип файла {detected}, а заявлен {declared_type.lower()}"
        )
    return detected


def validate_video_content(content: bytes, declared_type: str) -> str:
    """Проверяет, что видео реально является MP4, MOV или WebM."""

    detected = detect_video_type(content)
    if detected is None:
        raise MediaValidationError(
            "Содержимое файла не похоже на MP4, MOV или WebM"
        )
    if detected != declared_type.lower():
        raise MediaValidationError(
            f"Фактический тип файла {detected}, а заявлен {declared_type.lower()}"
        )
    return detected
