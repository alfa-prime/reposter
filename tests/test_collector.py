import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import news_reposter.services.collector as collector_module
from news_reposter.db.models import AttachmentType
from news_reposter.integrations.vk import VKPost
from news_reposter.services.collector import build_post_attachments


class FakeSession:
    """Минимальная сессия для проверки полного прохода сборщика."""

    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self.rows = rows
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def execute(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self.rows)


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *_args: object) -> None:
        return None


def test_collector_stores_all_ten_posts_after_last_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Все десять новых записей проходят от клиента VK до сохранения в очередь."""

    source = SimpleNamespace(source_id=1, url="https://vk.com/news_murmansk")
    target_source = SimpleNamespace(target_id=7)
    session = FakeSession([(target_source, source)])
    received_post_ids: list[int] = []

    class FakeVKClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def get_posts_after(self, _url: str, after_post_id: int) -> list[VKPost]:
            assert after_post_id == 100
            return [
                VKPost(
                    id=post_id,
                    owner_id=-123,
                    date=1_800_000_000 + post_id,
                    text=f"Пост {post_id}",
                )
                for post_id in range(101, 111)
            ]

    async def fake_store(**kwargs: object) -> tuple[bool, int]:
        vk_post = kwargs["vk_post"]
        assert isinstance(vk_post, VKPost)
        received_post_ids.append(vk_post.id)
        return True, 1

    monkeypatch.setattr(
        collector_module,
        "get_settings",
        lambda: SimpleNamespace(
            vk_access_token="secret",
            vk_api_version="5.199",
            vk_api_url="https://api.vk.com/method",
        ),
    )
    monkeypatch.setattr(
        collector_module,
        "async_session_factory",
        lambda: FakeSessionContext(session),
    )
    monkeypatch.setattr(collector_module, "VKClient", FakeVKClient)
    monkeypatch.setattr(
        collector_module,
        "_get_last_external_post_id",
        AsyncMock(return_value=100),
    )
    monkeypatch.setattr(collector_module, "_store_post_and_queue_items", fake_store)

    summary = asyncio.run(collector_module.collect_active_sources_once())

    assert received_post_ids == list(range(101, 111))
    assert summary == {
        "sources_checked": 1,
        "posts_created": 10,
        "queue_items_created": 10,
        "errors": 0,
    }
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


def test_collector_serializes_manual_and_scheduled_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ручной и плановый запуск не выполняют сбор одновременно."""

    active_runs = 0
    max_active_runs = 0

    async def fake_collect() -> dict[str, int]:
        nonlocal active_runs, max_active_runs
        active_runs += 1
        max_active_runs = max(max_active_runs, active_runs)
        await asyncio.sleep(0)
        active_runs -= 1
        return {
            "sources_checked": 0,
            "posts_created": 0,
            "queue_items_created": 0,
            "errors": 0,
        }

    monkeypatch.setattr(collector_module, "_collect_active_sources_once", fake_collect)

    async def scenario() -> None:
        await asyncio.gather(
            collector_module.collect_active_sources_once(),
            collector_module.collect_active_sources_once(),
        )

    asyncio.run(scenario())

    assert max_active_runs == 1


def test_build_post_attachments_keeps_photos_and_videos_in_order() -> None:
    """Сохраняет фотографии и видео, не меняя их порядок."""

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
                "video": {
                    "id": 20,
                    "owner_id": -123,
                    "title": "Видео",
                    "player": "https://vk.com/video_ext.php?oid=-123&id=20",
                },
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

    assert len(attachments) == 3
    assert [item.position for item in attachments] == [0, 1, 2]
    assert [item.attachment_type for item in attachments] == [
        AttachmentType.PHOTO,
        AttachmentType.VIDEO,
        AttachmentType.PHOTO,
    ]
    assert attachments[0].external_attachment_id == "-123_10"
    assert attachments[0].source_url == "https://img/1-big.jpg"
    assert attachments[1].external_attachment_id == "-123_20"
    assert attachments[1].source_url == "https://vk.com/video_ext.php?oid=-123&id=20"
    assert attachments[2].external_attachment_id == "-123_11"
    assert attachments[2].source_url == "https://img/2-original.jpg"


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
