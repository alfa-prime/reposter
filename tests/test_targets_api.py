import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

import news_reposter.api.v1.targets as targets_api
from news_reposter.main import app
from news_reposter.repositories import TargetAlreadyExistsError
from news_reposter.schemas import TargetCreate, TargetUpdate


class MemoryTargetRepository:
    """Хранит цели публикаций в памяти во время проверки API."""

    records: dict[int, SimpleNamespace] = {}
    next_id = 1

    def __init__(self, _session: object) -> None:
        """Принимает совместимый с настоящим репозиторием аргумент."""

    @classmethod
    def reset(cls) -> None:
        """Очищает записи перед запуском сценария."""

        cls.records = {}
        cls.next_id = 1

    async def create(self, data: TargetCreate) -> SimpleNamespace:
        """Создаёт тестовую цель с проверкой составной уникальности."""

        if any(
            item.platform == data.platform and item.external_id == data.external_id
            for item in self.records.values()
        ):
            raise TargetAlreadyExistsError
        now = datetime.now(UTC)
        target = SimpleNamespace(
            target_id=self.next_id,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self.records[target.target_id] = target
        type(self).next_id += 1
        return target

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        platform: str | None,
        is_active: bool | None,
    ) -> list[SimpleNamespace]:
        """Возвращает отфильтрованный участок тестовых целей."""

        records = list(self.records.values())
        if platform is not None:
            records = [item for item in records if item.platform == platform]
        if is_active is not None:
            records = [item for item in records if item.is_active == is_active]
        return records[offset : offset + limit]

    async def get(self, target_id: int) -> SimpleNamespace | None:
        """Находит тестовую цель по идентификатору."""

        return self.records.get(target_id)

    async def update(
        self,
        target: SimpleNamespace,
        data: TargetUpdate,
    ) -> SimpleNamespace:
        """Изменяет поля тестовой цели."""

        changes = data.model_dump(exclude_unset=True)
        platform = changes.get("platform", target.platform)
        external_id = changes.get("external_id", target.external_id)
        if any(
            item.target_id != target.target_id
            and item.platform == platform
            and item.external_id == external_id
            for item in self.records.values()
        ):
            raise TargetAlreadyExistsError
        for field, value in changes.items():
            setattr(target, field, value)
        target.updated_at = datetime.now(UTC)
        return target

    async def delete(self, target: SimpleNamespace) -> None:
        """Удаляет тестовую цель."""

        self.records.pop(target.target_id)


@pytest.fixture
def memory_target_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подменяет репозиторий целей хранилищем в памяти."""

    MemoryTargetRepository.reset()
    monkeypatch.setattr(targets_api, "TargetRepository", MemoryTargetRepository)


def test_targets_crud(memory_target_repository: None) -> None:
    """Проверяет полный цикл управления целями через HTTP API."""

    async def scenario() -> None:
        """Отправляет CRUD-запросы приложению."""

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/v1/targets",
                json={
                    "name": " Новости 51 региона ",
                    "platform": "MAX",
                    "external_id": " -77162942582085 ",
                    "url": " https://max.ru/channel_51_news ",
                },
            )
            assert created.status_code == 201
            target = created.json()
            assert target["target_id"] == 1
            assert target["platform"] == "max"
            assert target["external_id"] == "-77162942582085"
            assert target["is_active"] is True

            duplicate = await client.post(
                "/api/v1/targets",
                json={
                    "name": "Дубль",
                    "platform": "max",
                    "external_id": "-77162942582085",
                },
            )
            assert duplicate.status_code == 409

            updated = await client.patch(
                "/api/v1/targets/1",
                json={"name": "Основной канал", "url": None, "is_active": False},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Основной канал"
            assert updated.json()["url"] is None
            assert updated.json()["is_active"] is False

            filtered = await client.get(
                "/api/v1/targets",
                params={"platform": "MAX", "is_active": "false"},
            )
            assert filtered.status_code == 200
            assert [item["target_id"] for item in filtered.json()] == [1]

            deleted = await client.delete("/api/v1/targets/1")
            assert deleted.status_code == 204

            missing = await client.get("/api/v1/targets/1")
            assert missing.status_code == 404

    asyncio.run(scenario())


def test_target_validation(memory_target_repository: None) -> None:
    """Проверяет обязательные поля и необязательную ссылку цели."""

    async def scenario() -> None:
        """Отправляет допустимые и ошибочные запросы."""

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            without_url = await client.post(
                "/api/v1/targets",
                json={"name": "Канал", "platform": "max", "external_id": "-1"},
            )
            assert without_url.status_code == 201
            assert without_url.json()["url"] is None

            invalid_url = await client.patch(
                "/api/v1/targets/1",
                json={"url": "max.ru/channel"},
            )
            assert invalid_url.status_code == 422

            null_name = await client.patch(
                "/api/v1/targets/1",
                json={"name": None},
            )
            assert null_name.status_code == 422

    asyncio.run(scenario())
