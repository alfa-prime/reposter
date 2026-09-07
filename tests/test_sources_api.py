import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

import news_reposter.api.v1.sources as sources_api
from news_reposter.main import app
from news_reposter.repositories import SourceAlreadyExistsError
from news_reposter.schemas import SourceCreate, SourceUpdate


class MemorySourceRepository:
    """Хранит источники в памяти во время проверки HTTP API."""

    records: dict[int, SimpleNamespace] = {}
    next_id = 1

    def __init__(self, _session: object) -> None:
        """Принимает совместимый с настоящим репозиторием аргумент."""

    @classmethod
    def reset(cls) -> None:
        """Очищает записи перед запуском нового сценария."""

        cls.records = {}
        cls.next_id = 1

    async def create(self, data: SourceCreate) -> SimpleNamespace:
        """Создаёт тестовый источник и проверяет уникальность ссылки."""

        if any(source.url == data.url for source in self.records.values()):
            raise SourceAlreadyExistsError
        now = datetime.now(UTC)
        source = SimpleNamespace(
            id=self.next_id,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self.records[source.id] = source
        type(self).next_id += 1
        return source

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        platform: str | None,
        is_active: bool | None,
    ) -> list[SimpleNamespace]:
        """Возвращает отфильтрованный участок тестовых записей."""

        records = list(self.records.values())
        if platform is not None:
            records = [item for item in records if item.platform == platform]
        if is_active is not None:
            records = [item for item in records if item.is_active == is_active]
        return records[offset : offset + limit]

    async def get(self, source_id: int) -> SimpleNamespace | None:
        """Находит тестовый источник по идентификатору."""

        return self.records.get(source_id)

    async def update(
        self,
        source: SimpleNamespace,
        data: SourceUpdate,
    ) -> SimpleNamespace:
        """Изменяет поля тестового источника."""

        changes = data.model_dump(exclude_unset=True)
        new_url = changes.get("url")
        if new_url is not None and any(
            item.id != source.id and item.url == new_url
            for item in self.records.values()
        ):
            raise SourceAlreadyExistsError
        for field, value in changes.items():
            setattr(source, field, value)
        source.updated_at = datetime.now(UTC)
        return source

    async def delete(self, source: SimpleNamespace) -> None:
        """Удаляет тестовый источник."""

        self.records.pop(source.id)


@pytest.fixture
def memory_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подменяет репозиторий API хранилищем в памяти."""

    MemorySourceRepository.reset()
    monkeypatch.setattr(sources_api, "SourceRepository", MemorySourceRepository)


def test_sources_crud(memory_repository: None) -> None:
    """Проверяет полный цикл управления источниками через HTTP API."""

    async def scenario() -> None:
        """Отправляет CRUD-запросы приложению."""

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/v1/sources",
                json={
                    "name": " Полуостров 51 ",
                    "platform": "VK",
                    "url": " https://vk.ru/peninsula51 ",
                },
            )
            assert created.status_code == 201
            source = created.json()
            assert source["id"] == 1
            assert source["name"] == "Полуостров 51"
            assert source["platform"] == "vk"
            assert source["is_active"] is True

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
                    "platform": "rss",
                    "url": "https://example.com/feed.xml",
                    "is_active": False,
                },
            )
            assert second.status_code == 201

            filtered = await client.get(
                "/api/v1/sources",
                params={"is_active": "false"},
            )
            assert filtered.status_code == 200
            assert [item["name"] for item in filtered.json()] == [
                "Резервный источник"
            ]

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
        """Отправляет запросы, которые не должны доходить до репозитория."""

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
