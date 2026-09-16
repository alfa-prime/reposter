import base64

import pytest
from pydantic import ValidationError

from news_reposter.api.v1.queue_video import QueueVideoUpload
from news_reposter.schemas.queue_item import QueueMediaUpload
from news_reposter.services.media_validation import (
    MediaValidationError,
    detect_image_type,
    detect_video_type,
    validate_image_content,
    validate_video_content,
)

JPEG = b"\xff\xd8\xff" + b"jpeg-data"
PNG = b"\x89PNG\r\n\x1a\n" + b"png-data"
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"webp-data"
MP4 = b"\x00\x00\x00\x18ftypisom" + b"mp4-data"
MOV = b"\x00\x00\x00\x18ftypqt  " + b"mov-data"
WEBM = b"\x1aE\xdf\xa3" + b"header-webm-data"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (JPEG, "image/jpeg"),
        (PNG, "image/png"),
        (WEBP, "image/webp"),
        (b"not-an-image", None),
    ],
)
def test_detect_image_type(content: bytes, expected: str | None) -> None:
    assert detect_image_type(content) == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (MP4, "video/mp4"),
        (MOV, "video/quicktime"),
        (WEBM, "video/webm"),
        (b"not-a-video", None),
    ],
)
def test_detect_video_type(content: bytes, expected: str | None) -> None:
    assert detect_video_type(content) == expected


def test_media_validation_rejects_unknown_and_mismatched_types() -> None:
    with pytest.raises(MediaValidationError, match="не похоже"):
        validate_image_content(b"invalid", "image/png")
    with pytest.raises(MediaValidationError, match="Фактический тип"):
        validate_image_content(PNG, "image/jpeg")
    with pytest.raises(MediaValidationError, match="не похоже"):
        validate_video_content(b"invalid", "video/mp4")
    with pytest.raises(MediaValidationError, match="Фактический тип"):
        validate_video_content(MP4, "video/webm")


def test_upload_schemas_validate_real_file_signatures() -> None:
    image = QueueMediaUpload(
        filename="photo.png",
        content_type="image/png",
        data_base64=base64.b64encode(PNG).decode(),
    )
    video = QueueVideoUpload(
        filename="clip.mp4",
        content_type="video/mp4",
        data_base64=base64.b64encode(MP4).decode(),
    )

    assert image.filename == "photo.png"
    assert video.filename == "clip.mp4"

    with pytest.raises(ValidationError, match="Фактический тип"):
        QueueMediaUpload(
            filename="fake.jpg",
            content_type="image/jpeg",
            data_base64=base64.b64encode(PNG).decode(),
        )
    with pytest.raises(ValidationError, match="Base64"):
        QueueVideoUpload(
            filename="broken.mp4",
            content_type="video/mp4",
            data_base64="not-base64!",
        )
