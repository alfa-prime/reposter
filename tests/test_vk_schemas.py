from news_reposter.integrations.vk.schemas import VKPost


def test_photo_urls_prefers_original_and_falls_back_to_largest_size() -> None:
    """Проверяет выбор оригинала и запасной выбор крупнейшего размера."""

    post = VKPost(
        id=1,
        owner_id=-1,
        date=1_700_000_000,
        attachments=[
            {
                "type": "photo",
                "photo": {
                    "orig_photo": {"url": "https://example.com/original.jpg"},
                    "sizes": [{"width": 100, "height": 100, "url": "small"}],
                },
            },
            {
                "type": "photo",
                "photo": {
                    "sizes": [
                        {"width": 100, "height": 100, "url": "small"},
                        {"width": 1000, "height": 800, "url": "large"},
                    ]
                },
            },
            {"type": "video", "video": {"id": 2}},
        ],
    )

    assert post.photo_urls() == ["https://example.com/original.jpg", "large"]
