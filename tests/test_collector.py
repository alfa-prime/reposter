from news_reposter.db.models import AttachmentType
from news_reposter.services.collector import build_post_attachments


def test_build_post_attachments_preserves_order_and_types() -> None:
    """Сохраняет порядок фото, видео и ссылки из исходного поста VK."""

    attachments = build_post_attachments(
        [
            {
                "type": "photo",
                "photo": {
                    "id": 10,
                    "owner_id": -123,
                    "sizes": [
                        {"url": "https://img/small.jpg", "width": 100, "height": 100},
                        {"url": "https://img/big.jpg", "width": 1200, "height": 800},
                    ],
                },
            },
            {
                "type": "video",
                "video": {
                    "id": 20,
                    "owner_id": -123,
                    "title": "Видео",
                },
            },
            {
                "type": "link",
                "link": {
                    "url": "https://example.com/news",
                    "title": "Новость",
                },
            },
        ]
    )

    assert [item.position for item in attachments] == [0, 1, 2]
    assert [item.attachment_type for item in attachments] == [
        AttachmentType.PHOTO,
        AttachmentType.VIDEO,
        AttachmentType.LINK,
    ]
    assert attachments[0].external_attachment_id == "-123_10"
    assert attachments[0].source_url == "https://img/big.jpg"
    assert attachments[1].external_attachment_id == "-123_20"
    assert attachments[1].source_url == "https://vk.com/video-123_20"
    assert attachments[2].source_url == "https://example.com/news"


def test_build_post_attachments_keeps_unknown_payload() -> None:
    """Неизвестный тип не теряется и сохраняется как OTHER вместе с raw_data."""

    raw = {"type": "poll", "poll": {"id": 77, "question": "Вопрос?"}}
    attachments = build_post_attachments([raw])

    assert len(attachments) == 1
    assert attachments[0].attachment_type == AttachmentType.OTHER
    assert attachments[0].external_attachment_id == "77"
    assert attachments[0].source_url is None
    assert attachments[0].raw_data == raw
