from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from news_reposter.api.dependencies import require_api_key
from news_reposter.db.session import get_db_session
from news_reposter.main import app
from news_reposter.repositories.source import SourceAlreadyExistsError
from news_reposter.schemas.source import SourceCreate, SourceUpdate


class MemorySourceRepository:
    """Простой in-memory репозиторий для API-тестов источников."""

    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self.next_id = 1

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        platform: str | None = None,
        is_active: bool | None = None,
    ) -> list[dict[str, Any]]:
        values = list(self.items.values())
        if platform is not None:
            values = [item for item in values if item["platform"] == platform]
        if is_active is not None:
            values = [item for item in values if item["is_active"] is is_active]
        return values[offset : offset + limit]

    async def get(self, source_id: int) -> dict[str, Any] | None:
        return self.items.get(source_id)

    async def queue_item_ids(self, _source_id: int) -> list[int]:
        return []

    async def create(self, data: SourceCreate) -> dict[str, Any]:
        normalized_url = str(data.url).replace("vk.ru", "vk.com")
        if any(
            str(item["url"]).replace("vk.ru", "vk.com") == normalized_url
            for item in self.items.values()
        ):
            raise SourceAlreadyExistsError("Источник с такой ссылкой уже существует")

        now = datetime.now(UTC)
        item = {
            "source_id": self.next_id,
            "name": data.name,
            "platform": data.platform,
            "url": str(data.url),
            "is_active": data.is_active,
            "created_at": now,
            "updated_at": now,
        }
        self.items[self.next_id] = item
        self.next_id += 1
        return item

    async def update(
        self,
        source: dict[str, Any],
        data: SourceUpdate,
    ) -> dict[str, Any]:
        payload = data.model_dump(exclude_unset=True)
        if "url" in payload and payload["url"] is not None:
            payload["url"] = str(payload["url"])
        source.update(payload)
        source["updated_at"] = datetime.now(UTC)
        return source

    async def delete(self, source: dict[str, Any]) -> None:
        self.items.pop(int(source["source_id"]), None)


@pytest.fixture
def memory_repository(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Подменяет API-key, SQLAlchemy-сессию и репозиторий in-memory реализацией."""

    repository = MemorySourceRepository()

    async def fake_session() -> AsyncIterator[object]:
        yield object()

    async def allow_api_key() -> None:
        return None

    app.dependency_overrides[get_db_session] = fake_session
    app.dependency_overrides[require_api_key] = allow_api_key
    monkeypatch.setattr(
        "news_reposter.api.v1.sources.SourceRepository",
        lambda _session: repository,
    )

    yield
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(require_api_key, None)


def test_sources_crud(memory_repository: None) -> None:
    """Проверяет основной CRUD источников и фильтрацию по активности."""

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/v1/sources",
                json={
                    "name": "Полуостров 51",
                    "platform": "vk",
                    "url": "https://vk.com/peninsula51",
                },
            )
            assert created.status_code == 201
            source = created.json()
            assert source["source_id"] == 1
            assert source["name"] == "Полуостров 51"
            assert source["platform"] == "vk"
            assert source["is_active"] is True
            assert source["created_at"]
            assert source["updated_at"]

            duplicate = await client.post(
                "/api/v1/sources",
                json={
                    "name": "Дубль",
                    "platform": "vk",
                    "url": "https://vk.ru/peninsula51",
                },
            )
            assert duplicate.status_code == 409

            second = await client.post(
                "/api/v1/sources",
                json={
                    "name": "Резервный источник",
                    "platform": "telegram",
                    "url": "https://t.me/reserve_feed",
                    "is_active": False,
                },
            )
            assert second.status_code == 201

            filtered = await client.get(
                "/api/v1/sources",
                params={"is_active": "false"},
            )
            assert filtered.status_code == 200
            assert [item["name"] for item in filtered.json()] == ["Резервный источник"]

            updated = await client.patch(
                "/api/v1/sources/1",
                json={"name": "Новости 51 региона", "is_active": False},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Новости 51 региона"
            assert updated.json()["is_active"] is False

            empty_update = await client.patch("/api/v1/sources/1", json={})
            assert empty_update.status_code == 422

            deleted = await client.delete("/api/v1/sources/1")
            assert deleted.status_code == 204
            assert deleted.content == b""

            missing = await client.get("/api/v1/sources/1")
            assert missing.status_code == 404
            assert missing.json()["detail"] == "Источник не найден"

    asyncio.run(scenario())


def test_source_validation(memory_repository: None) -> None:
    """Проверяет отказ для некорректной ссылки и пустого обязательного поля."""

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            invalid_url = await client.post(
                "/api/v1/sources",
                json={"name": "Источник", "platform": "vk", "url": "vk.ru/test"},
            )
            assert invalid_url.status_code == 422

            null_update = await client.patch(
                "/api/v1/sources/1",
                json={"name": None},
            )
            assert null_update.status_code == 422

    asyncio.run(scenario())
