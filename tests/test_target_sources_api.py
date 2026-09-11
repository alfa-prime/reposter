import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

import news_reposter.api.v1.target_sources as target_sources_api
from news_reposter.api.dependencies import require_api_key
from news_reposter.main import app
from news_reposter.repositories import TargetSourceAlreadyExistsError
from news_reposter.schemas import TargetSourceCreate, TargetSourceUpdate


class MemoryTargetSourceRepository:
    """Хранит связи целей и источников в памяти во время проверки API."""

    records: dict[int, SimpleNamespace] = {}
    next_id = 1
    target_ids = {1}
    source_ids = {10, 20}

    def __init__(self, _session: object) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls.records = {}
        cls.next_id = 1

    async def target_exists(self, target_id: int) -> bool:
        return target_id in self.target_ids

    async def source_exists(self, source_id: int) -> bool:
        return source_id in self.source_ids

    async def create(
        self,
        target_id: int,
        data: TargetSourceCreate,
    ) -> SimpleNamespace:
        if any(
            item.target_id == target_id and item.source_id == data.source_id
            for item in self.records.values()
        ):
            raise TargetSourceAlreadyExistsError
        now = datetime.now(UTC)
        item = SimpleNamespace(
            target_source_id=self.next_id,
            target_id=target_id,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self.records[item.target_source_id] = item
        type(self).next_id += 1
        return item

    async def list(
        self,
        *,
        target_id: int,
        offset: int,
        limit: int,
        is_active: bool | None,
    ) -> list[SimpleNamespace]:
        items = [item for item in self.records.values() if item.target_id == target_id]
        if is_active is not None:
            items = [item for item in items if item.is_active == is_active]
        return items[offset : offset + limit]

    async def get(
        self,
        target_id: int,
        target_source_id: int,
    ) -> SimpleNamespace | None:
        item = self.records.get(target_source_id)
        if item is None or item.target_id != target_id:
            return None
        return item

    async def update(
        self,
        item: SimpleNamespace,
        data: TargetSourceUpdate,
    ) -> SimpleNamespace:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.updated_at = datetime.now(UTC)
        return item

    async def delete(self, item: SimpleNamespace) -> None:
        self.records.pop(item.target_source_id)


@pytest.fixture
def memory_target_source_repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def allow_api_key() -> None:
        pass

    MemoryTargetSourceRepository.reset()
    monkeypatch.setattr(
        target_sources_api,
        "TargetSourceRepository",
        MemoryTargetSourceRepository,
    )
    app.dependency_overrides[require_api_key] = allow_api_key
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_api_key, None)


def test_target_sources_crud(memory_target_source_repository: None) -> None:
    """Проверяет подключение и настройку источников конкретного канала."""

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/targets/1/sources",
                json={"source_id": 10, "rewrite_enabled": True},
            )
            assert created.status_code == 201
            assert created.json()["source_id"] == 10
            assert created.json()["is_active"] is True

            duplicate = await client.post(
                "/api/v1/targets/1/sources",
                json={"source_id": 10},
            )
            assert duplicate.status_code == 409

            missing_source = await client.post(
                "/api/v1/targets/1/sources",
                json={"source_id": 999},
            )
            assert missing_source.status_code == 404

            updated = await client.patch(
                "/api/v1/targets/1/sources/1",
                json={"rewrite_enabled": False, "is_active": False},
            )
            assert updated.status_code == 200
            assert updated.json()["rewrite_enabled"] is False
            assert updated.json()["is_active"] is False

            listed = await client.get(
                "/api/v1/targets/1/sources",
                params={"is_active": "false"},
            )
            assert listed.status_code == 200
            assert [item["target_source_id"] for item in listed.json()] == [1]

            deleted = await client.delete("/api/v1/targets/1/sources/1")
            assert deleted.status_code == 204

            missing = await client.patch(
                "/api/v1/targets/1/sources/1",
                json={"is_active": True},
            )
            assert missing.status_code == 404

    asyncio.run(scenario())
