from news_reposter.db.models import AttachmentType
from news_reposter.services.collector import build_post_attachments


def test_build_post_attachments_keeps_only_photos_in_order() -> None:
    """Для MVP сохраняет только фотографии, не меняя их порядок."""

    attachments = build_post_attachments(
        [
            {
                "type": "photo",
                "photo": {
                    "id": 10,
                    "owner_id": -123,
                    "sizes": [
                        {"url": "https://img/1-small.jpg", "width": 100, "height": 100},
                        {"url": "https://img/1-big.jpg", "width": 1200, "height": 800},
                    ],
                },
            },
            {
                "type": "video",
                "video": {"id": 20, "owner_id": -123, "title": "Видео"},
            },
            {
                "type": "photo",
                "photo": {
                    "id": 11,
                    "owner_id": -123,
                    "orig_photo": {"url": "https://img/2-original.jpg"},
                },
            },
            {
                "type": "link",
                "link": {"url": "https://example.com/news"},
            },
        ]
    )

    assert len(attachments) == 2
    assert [item.position for item in attachments] == [0, 1]
    assert [item.attachment_type for item in attachments] == [
        AttachmentType.PHOTO,
        AttachmentType.PHOTO,
    ]
    assert attachments[0].external_attachment_id == "-123_10"
    assert attachments[0].source_url == "https://img/1-big.jpg"
    assert attachments[1].external_attachment_id == "-123_11"
    assert attachments[1].source_url == "https://img/2-original.jpg"


def test_build_post_attachments_keeps_ten_photos() -> None:
    """Пост с десятью фотографиями доходит до хранения без потерь."""

    raw = [
        {
            "type": "photo",
            "photo": {
                "id": photo_id,
                "owner_id": -123,
                "orig_photo": {"url": f"https://img/{photo_id}.jpg"},
            },
        }
        for photo_id in range(1, 11)
    ]

    attachments = build_post_attachments(raw)

    assert len(attachments) == 10
    assert [item.position for item in attachments] == list(range(10))
    assert [item.source_url for item in attachments] == [
        f"https://img/{photo_id}.jpg" for photo_id in range(1, 11)
    ]
