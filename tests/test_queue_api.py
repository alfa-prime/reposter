from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock

import httpx
import pytest

import news_reposter.api.v1.queue as queue_api
from news_reposter.api.dependencies import get_current_auth
from news_reposter.auth.rbac import PermissionCode
from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import get_settings
from news_reposter.db.models import AttachmentType, QueueItemStatus
from news_reposter.main import app
from news_reposter.repositories.queue_item import QueueItemAlreadyExistsError
from news_reposter.schemas.queue_item import QueueItemCreate, QueueItemUpdate
from news_reposter.services import media_storage

CSRF_TOKEN = "queue-csrf-token"
CSRF_COOKIE_NAME = get_settings().auth_csrf_cookie_name
QUEUE_PERMISSIONS = frozenset(
    {
        PermissionCode.QUEUE_READ.value,
        PermissionCode.QUEUE_EDIT.value,
        PermissionCode.QUEUE_REWRITE.value,
        PermissionCode.QUEUE_SUBMIT.value,
        PermissionCode.QUEUE_MODERATE.value,
        PermissionCode.QUEUE_SCHEDULE.value,
        PermissionCode.QUEUE_PUBLISH.value,
    }
)


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

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        target_id: int | None,
        statuses: list[QueueItemStatus],
    ) -> list[SimpleNamespace]:
        records = list(self.records.values())
        if target_id is not None:
            records = [item for item in records if item.target_id == target_id]
        records = [item for item in records if item.status in statuses]
        records.sort(key=lambda item: item.queue_item_id, reverse=True)
        return records[offset : offset + limit]

    async def count_by_status(
        self,
        *,
        target_id: int | None,
    ) -> dict[QueueItemStatus, int]:
        counts: dict[QueueItemStatus, int] = {}
        for item in self.records.values():
            if target_id is not None and item.target_id != target_id:
                continue
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

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
    async def allow_queue_access() -> SimpleNamespace:
        return SimpleNamespace(
            user=SimpleNamespace(user_id=1, must_change_password=False),
            session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
            permission_codes=QUEUE_PERMISSIONS,
        )

    MemoryQueueRepository.reset()
    monkeypatch.setattr(queue_api, "QueueItemRepository", MemoryQueueRepository)
    monkeypatch.setattr(queue_api, "record_editorial_event", AsyncMock())
    app.dependency_overrides[get_current_auth] = allow_queue_access
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_auth, None)


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
            transport=transport,
            base_url="http://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
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


def test_queue_page_returns_selected_statuses_and_counts(
    memory_queue_repository: None,
) -> None:
    """Постраничный endpoint фильтрует вкладку и возвращает общие счётчики."""

    now = datetime.now(UTC)
    statuses = [
        QueueItemStatus.PENDING,
        QueueItemStatus.REWRITING,
        QueueItemStatus.AWAITING_MODERATION,
        QueueItemStatus.PENDING,
    ]
    for queue_item_id, item_status in enumerate(statuses, start=1):
        MemoryQueueRepository.records[queue_item_id] = SimpleNamespace(
            queue_item_id=queue_item_id,
            post_id=queue_item_id,
            target_id=20,
            rewritten_text=f"Пост {queue_item_id}",
            status=item_status,
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
            response = await client.get(
                "/api/v1/queue/page",
                params=[
                    ("target_id", "20"),
                    ("status", "pending"),
                    ("status", "rewriting"),
                    ("offset", "1"),
                    ("limit", "2"),
                ],
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["offset"] == 1
        assert body["limit"] == 2
        assert [item["queue_item_id"] for item in body["items"]] == [2, 1]
        assert body["status_counts"] == {
            "pending": 2,
            "rewriting": 1,
            "awaiting_moderation": 1,
        }

    asyncio.run(scenario())


def test_queue_read_route_enforces_user_permission(
    memory_queue_repository: None,
) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
        ) as client:
            allowed = await client.get(
                "/api/v1/queue/page",
                params={"status": "pending"},
            )

            app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
                user=SimpleNamespace(must_change_password=False),
                permission_codes=frozenset({PermissionCode.SOURCES_READ.value}),
            )
            forbidden = await client.get(
                "/api/v1/queue/page",
                params={"status": "pending"},
            )

            app.dependency_overrides.pop(get_current_auth, None)
            unauthorized = await client.get(
                "/api/v1/queue/page",
                params={"status": "pending"},
            )

        assert allowed.status_code == 200
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": "Недостаточно прав"}
        assert unauthorized.status_code == 401
        assert unauthorized.json() == {"detail": "Требуется вход"}

    asyncio.run(scenario())


def test_submit_requires_prepared_text(memory_queue_repository: None) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
        ) as client:
            created = await client.post(
                "/api/v1/queue",
                json={"post_id": 10, "target_id": 20},
            )
            assert created.status_code == 201

            submitted = await client.post("/api/v1/queue/1/submit")
            assert submitted.status_code == 409

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("method", "path", "payload", "required_permission"),
    [
        (
            "POST",
            "/api/v1/queue",
            {"post_id": 10, "target_id": 20},
            PermissionCode.QUEUE_EDIT,
        ),
        (
            "POST",
            "/api/v1/queue/1/rewrite",
            None,
            PermissionCode.QUEUE_REWRITE,
        ),
        (
            "POST",
            "/api/v1/queue/1/submit",
            None,
            PermissionCode.QUEUE_SUBMIT,
        ),
        (
            "POST",
            "/api/v1/queue/1/approve",
            None,
            PermissionCode.QUEUE_MODERATE,
        ),
        (
            "POST",
            "/api/v1/queue/1/schedule",
            {"scheduled_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
            PermissionCode.QUEUE_SCHEDULE,
        ),
        (
            "POST",
            "/api/v1/queue/1/publish-now",
            None,
            PermissionCode.QUEUE_PUBLISH,
        ),
    ],
)
def test_queue_mutation_requires_its_permission(
    memory_queue_repository: None,
    method: str,
    path: str,
    payload: dict[str, object] | None,
    required_permission: PermissionCode,
) -> None:
    async def scenario() -> None:
        app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
            user=SimpleNamespace(must_change_password=False),
            session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
            permission_codes=QUEUE_PERMISSIONS - {required_permission.value},
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
        ) as client:
            response = await client.request(method, path, json=payload)

        assert response.status_code == 403
        assert response.json() == {"detail": "Недостаточно прав"}

    asyncio.run(scenario())


def test_queue_mutation_requires_csrf_and_same_origin(
    memory_queue_repository: None,
) -> None:
    payload = {"post_id": 10, "target_id": 20}

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
        ) as client:
            missing_csrf = await client.post("/api/v1/queue", json=payload)
            foreign_origin = await client.post(
                "/api/v1/queue",
                json=payload,
                headers={
                    "X-CSRF-Token": CSRF_TOKEN,
                    "Origin": "https://evil.example",
                },
            )

        assert missing_csrf.status_code == 403
        assert missing_csrf.json() == {"detail": "Недействительный CSRF-токен"}
        assert foreign_origin.status_code == 403
        assert foreign_origin.json() == {"detail": "Недопустимый источник запроса"}

    asyncio.run(scenario())
