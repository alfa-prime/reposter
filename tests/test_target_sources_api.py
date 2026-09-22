import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import ClassVar

import httpx
import pytest

import news_reposter.api.v1.target_sources as target_sources_api
from news_reposter.api.dependencies import get_current_auth
from news_reposter.auth.rbac import PermissionCode
from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import get_settings
from news_reposter.main import app
from news_reposter.repositories import TargetSourceAlreadyExistsError
from news_reposter.schemas import TargetSourceCreate, TargetSourceUpdate

CSRF_TOKEN = "target-sources-csrf-token"
CSRF_COOKIE_NAME = get_settings().auth_csrf_cookie_name


class MemoryTargetSourceRepository:
    """Хранит связи целей и источников в памяти во время проверки API."""

    records: ClassVar[dict[int, SimpleNamespace]] = {}
    next_id: ClassVar[int] = 1
    target_ids: ClassVar[set[int]] = {1}
    source_ids: ClassVar[set[int]] = {10, 20}

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
    async def allow_directory_read() -> SimpleNamespace:
        return SimpleNamespace(
            user=SimpleNamespace(must_change_password=False),
            session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
            permission_codes=frozenset(
                {
                    PermissionCode.SOURCES_READ.value,
                    PermissionCode.TARGETS_READ.value,
                    PermissionCode.TARGETS_MANAGE.value,
                }
            ),
        )

    MemoryTargetSourceRepository.reset()
    monkeypatch.setattr(
        target_sources_api,
        "TargetSourceRepository",
        MemoryTargetSourceRepository,
    )
    app.dependency_overrides[get_current_auth] = allow_directory_read
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_auth, None)


def test_target_sources_crud(memory_target_source_repository: None) -> None:
    """Проверяет подключение и настройку источников конкретного канала."""

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
        ) as client:
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


def test_target_sources_read_requires_both_permissions(
    memory_target_source_repository: None,
) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
        ) as client:
            allowed = await client.get("/api/v1/targets/1/sources")

            app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
                user=SimpleNamespace(must_change_password=False),
                permission_codes=frozenset({PermissionCode.TARGETS_READ.value}),
            )
            missing_sources = await client.get("/api/v1/targets/1/sources")

            app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
                user=SimpleNamespace(must_change_password=False),
                permission_codes=frozenset({PermissionCode.SOURCES_READ.value}),
            )
            missing_targets = await client.get("/api/v1/targets/1/sources")

            app.dependency_overrides.pop(get_current_auth, None)
            unauthorized = await client.get("/api/v1/targets/1/sources")

        assert allowed.status_code == 200
        assert missing_sources.status_code == 403
        assert missing_targets.status_code == 403
        assert unauthorized.status_code == 401

    asyncio.run(scenario())


def test_target_sources_manage_requires_permission_and_csrf(
    memory_target_source_repository: None,
) -> None:
    payload = {"source_id": 10}

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
        ) as client:
            missing_csrf = await client.post(
                "/api/v1/targets/1/sources",
                json=payload,
            )

            app.dependency_overrides[get_current_auth] = lambda: SimpleNamespace(
                user=SimpleNamespace(must_change_password=False),
                session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
                permission_codes=frozenset(
                    {
                        PermissionCode.SOURCES_READ.value,
                        PermissionCode.TARGETS_READ.value,
                    }
                ),
            )
            forbidden = await client.post(
                "/api/v1/targets/1/sources",
                json=payload,
                headers={"X-CSRF-Token": CSRF_TOKEN},
            )

        assert missing_csrf.status_code == 403
        assert missing_csrf.json() == {"detail": "Недействительный CSRF-токен"}
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": "Недостаточно прав"}

    asyncio.run(scenario())
