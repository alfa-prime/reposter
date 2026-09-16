import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar

import httpx
import pytest

import news_reposter.api.v1.queue as queue_api
from news_reposter.api.dependencies import require_api_key
from news_reposter.db.models import AttachmentType, QueueItemStatus
from news_reposter.main import app
from news_reposter.repositories.queue_item import QueueItemAlreadyExistsError
from news_reposter.schemas.queue_item import QueueItemCreate, QueueItemUpdate
from news_reposter.services import media_storage


class MemoryQueueRepository:
    """Хранит элементы очереди в памяти во время API-тестов."""

    records: ClassVar[dict[int, SimpleNamespace]] = {}
    next_id: ClassVar[int] = 1

    def __init__(self, _session: object) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls.records = {}
        cls.next_id = 1

    async def post_exists(self, post_id: int) -> bool:
        return post_id == 10

    async def target_exists(self, target_id: int) -> bool:
        return target_id == 20

    async def create(self, data: QueueItemCreate) -> SimpleNamespace:
        if any(
            item.post_id == data.post_id and item.target_id == data.target_id
            for item in self.records.values()
        ):
            raise QueueItemAlreadyExistsError
        now = datetime.now(UTC)
        item = SimpleNamespace(
            queue_item_id=self.next_id,
            status=QueueItemStatus.PENDING,
            scheduled_at=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self.records[item.queue_item_id] = item
        type(self).next_id += 1
        return item

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        target_id: int | None,
        post_id: int | None,
        source_id: int | None,
        status: QueueItemStatus | None,
    ) -> list[SimpleNamespace]:
        del source_id
        records = list(self.records.values())
        if target_id is not None:
            records = [item for item in records if item.target_id == target_id]
        if post_id is not None:
            records = [item for item in records if item.post_id == post_id]
        if status is not None:
            records = [item for item in records if item.status == status]
        records.sort(key=lambda item: item.queue_item_id, reverse=True)
        return records[offset : offset + limit]

    async def get(self, queue_item_id: int) -> SimpleNamespace | None:
        return self.records.get(queue_item_id)

    async def update(
        self,
        item: SimpleNamespace,
        data: QueueItemUpdate,
    ) -> SimpleNamespace:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.updated_at = datetime.now(UTC)
        return item

    async def set_status(
        self,
        item: SimpleNamespace,
        new_status: QueueItemStatus,
        *,
        scheduled_at: datetime | None = None,
    ) -> SimpleNamespace:
        item.status = new_status
        item.scheduled_at = scheduled_at
        item.error_message = None
        item.updated_at = datetime.now(UTC)
        return item

    async def delete(self, item: SimpleNamespace) -> None:
        self.records.pop(item.queue_item_id)


@pytest.fixture
def memory_queue_repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def allow_api_key() -> None:
        pass

    MemoryQueueRepository.reset()
    monkeypatch.setattr(queue_api, "QueueItemRepository", MemoryQueueRepository)
    app.dependency_overrides[require_api_key] = allow_api_key
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_api_key, None)


def test_queue_response_includes_source_post_photos_and_target() -> None:
    now = datetime.now(UTC)
    item = SimpleNamespace(
        queue_item_id=1,
        post_id=10,
        target_id=20,
        rewritten_text="Подготовленный текст",
        status=QueueItemStatus.PENDING,
        scheduled_at=None,
        created_at=now,
        updated_at=now,
        error_message=None,
        target=SimpleNamespace(
            name="MAX Мурманск",
            platform="max",
            url="https://max.ru/murmansk",
        ),
        post=SimpleNamespace(
            original_text="Исходный текст",
            source_url="https://vk.com/wall-1_2",
            source_published_at=now,
            attachments=[
                SimpleNamespace(
                    attachment_id=11,
                    attachment_type=AttachmentType.PHOTO,
                    external_attachment_id="-1_100",
                    source_url="https://img/1.jpg",
                    position=0,
                ),
                SimpleNamespace(
                    attachment_id=12,
                    attachment_type=AttachmentType.OTHER,
                    external_attachment_id="77",
                    source_url=None,
                    position=1,
                ),
                SimpleNamespace(
                    attachment_id=13,
                    attachment_type=AttachmentType.PHOTO,
                    external_attachment_id="-1_101",
                    source_url="https://img/2.jpg",
                    position=2,
                ),
            ],
        ),
    )

    response = queue_api.queue_item_response(item)

    assert response.original_text == "Исходный текст"
    assert response.source_url == "https://vk.com/wall-1_2"
    assert response.target_name == "MAX Мурманск"
    assert response.target_platform == "max"
    assert response.target_url == "https://max.ru/murmansk"
    assert [photo.source_url for photo in response.photos] == [
        "https://img/1.jpg",
        "https://img/2.jpg",
    ]
    assert [photo.position for photo in response.photos] == [0, 2]


def test_queue_crud_and_moderation(
    memory_queue_repository: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media_storage, "MEDIA_ROOT", tmp_path)

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            missing_post = await client.post(
                "/api/v1/queue",
                json={"post_id": 999, "target_id": 20},
            )
            assert missing_post.status_code == 404

            created = await client.post(
                "/api/v1/queue",
                json={"post_id": 10, "target_id": 20},
            )
            assert created.status_code == 201
            assert created.json()["status"] == "pending"
            assert created.json()["photos"] == []

            duplicate = await client.post(
                "/api/v1/queue",
                json={"post_id": 10, "target_id": 20},
            )
            assert duplicate.status_code == 409

            edited = await client.patch(
                "/api/v1/queue/1",
                json={"rewritten_text": "Подготовленный текст"},
            )
            assert edited.status_code == 200
            assert edited.json()["rewritten_text"] == "Подготовленный текст"

            submitted = await client.post("/api/v1/queue/1/submit")
            assert submitted.status_code == 200
            assert submitted.json()["status"] == "awaiting_moderation"

            approved = await client.post("/api/v1/queue/1/approve")
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"

            past_schedule = await client.post(
                "/api/v1/queue/1/schedule",
                json={
                    "scheduled_at": (
                        datetime.now(UTC) - timedelta(minutes=1)
                    ).isoformat()
                },
            )
            assert past_schedule.status_code == 422
            assert "должны быть в будущем" in str(past_schedule.json()["detail"])

            scheduled_at = datetime.now(UTC) + timedelta(hours=2)
            scheduled = await client.post(
                "/api/v1/queue/1/schedule",
                json={"scheduled_at": scheduled_at.isoformat()},
            )
            assert scheduled.status_code == 200
            assert scheduled.json()["status"] == "scheduled"

            filtered = await client.get(
                "/api/v1/queue",
                params={"target_id": 20, "status": "scheduled"},
            )
            assert filtered.status_code == 200
            assert [item["queue_item_id"] for item in filtered.json()] == [1]

            invalid_reject = await client.post("/api/v1/queue/1/reject")
            assert invalid_reject.status_code == 409

            reopened = await client.post("/api/v1/queue/1/reopen")
            assert reopened.status_code == 200
            assert reopened.json()["status"] == "pending"
            assert reopened.json()["scheduled_at"] is None

            item_directory = media_storage.queue_item_directory(1)
            video_directory = item_directory / "videos"
            video_directory.mkdir(parents=True)
            (item_directory / "photo.jpg").write_bytes(b"image")
            (video_directory / "clip.mp4").write_bytes(b"video")
            state_path = media_storage.media_state_path(1)
            state_path.parent.mkdir(parents=True)
            state_path.write_text("[]", encoding="utf-8")

            deleted = await client.delete("/api/v1/queue/1")
            assert deleted.status_code == 204
            assert (await client.get("/api/v1/queue/1")).status_code == 404
            assert not item_directory.exists()
            assert not state_path.exists()

    asyncio.run(scenario())


def test_queue_pages_are_returned_newest_first(
    memory_queue_repository: None,
) -> None:
    """Большая очередь отдаётся стабильными страницами от новых записей к старым."""

    now = datetime.now(UTC)
    for queue_item_id in range(1, 126):
        MemoryQueueRepository.records[queue_item_id] = SimpleNamespace(
            queue_item_id=queue_item_id,
            post_id=queue_item_id,
            target_id=20,
            rewritten_text=f"Пост {queue_item_id}",
            status=QueueItemStatus.PENDING,
            scheduled_at=None,
            created_at=now,
            updated_at=now,
            error_message=None,
        )

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            first_page = await client.get("/api/v1/queue", params={"limit": 100})
            second_page = await client.get(
                "/api/v1/queue",
                params={"offset": 100, "limit": 100},
            )

        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert [item["queue_item_id"] for item in first_page.json()] == list(
            range(125, 25, -1)
        )
        assert [item["queue_item_id"] for item in second_page.json()] == list(
            range(25, 0, -1)
        )

    asyncio.run(scenario())


def test_submit_requires_prepared_text(memory_queue_repository: None) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/queue",
                json={"post_id": 10, "target_id": 20},
            )
            assert created.status_code == 201

            submitted = await client.post("/api/v1/queue/1/submit")
            assert submitted.status_code == 409

    asyncio.run(scenario())
