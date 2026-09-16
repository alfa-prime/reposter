import asyncio
from datetime import UTC, datetime, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

import news_reposter.api.v1.collection as collection_api
from news_reposter.db.models import (
    CollectionRun,
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionSettings,
)
from news_reposter.schemas.collection import CollectionSettingsUpdate
from news_reposter.services.collection_history import safe_error_message


def make_settings() -> CollectionSettings:
    return CollectionSettings(
        collection_settings_id=1,
        enabled=False,
        interval_minutes=15,
        start_time=time(8),
        end_time=time(20),
        timezone="Europe/Moscow",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_schedule_schema_accepts_overnight_window() -> None:
    data = CollectionSettingsUpdate(
        enabled=True,
        interval_minutes=30,
        start_time=time(20),
        end_time=time(8),
        timezone="Europe/Moscow",
    )

    assert data.start_time == time(20)
    assert data.end_time == time(8)


def test_schedule_schema_rejects_equal_times_and_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="не должны совпадать"):
        CollectionSettingsUpdate(
            enabled=True,
            interval_minutes=15,
            start_time=time(8),
            end_time=time(8),
            timezone="Europe/Moscow",
        )
    with pytest.raises(ValidationError, match="неизвестный часовой пояс"):
        CollectionSettingsUpdate(
            enabled=True,
            interval_minutes=15,
            start_time=time(8),
            end_time=time(20),
            timezone="Mars/Olympus",
        )


def test_update_settings_notifies_running_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_settings(self) -> CollectionSettings:
            return settings

        async def update_settings(
            self, model: CollectionSettings, **changes: object
        ) -> CollectionSettings:
            for field, value in changes.items():
                setattr(model, field, value)
            return model

    scheduler = SimpleNamespace(notify_settings_changed=lambda: calls.append(True))
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(collection_scheduler=scheduler))
    )
    calls: list[bool] = []
    monkeypatch.setattr(collection_api, "CollectionRepository", FakeRepository)
    data = CollectionSettingsUpdate(
        enabled=True,
        interval_minutes=30,
        start_time=time(20),
        end_time=time(8),
        timezone="Europe/Moscow",
    )

    result = asyncio.run(
        collection_api.update_collection_settings(data, request, None, None)
    )

    assert result.enabled is True
    assert result.start_time == time(20)
    assert calls == [True]


def test_collection_status_reports_next_run_and_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    settings.enabled = True
    latest = CollectionRun(
        collection_run_id=5,
        trigger=CollectionRunTrigger.SCHEDULED,
        status=CollectionRunStatus.FAILED,
        started_at=datetime.now(UTC),
        sources_total=1,
        sources_checked=1,
        sources_succeeded=0,
        sources_failed=1,
        posts_found=0,
        posts_created=0,
        queue_items_created=0,
    )

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_settings(self) -> CollectionSettings:
            return settings

        async def latest_run(self) -> CollectionRun:
            return latest

        async def latest_success(self) -> None:
            return None

        async def consecutive_failures(self) -> int:
            return 2

    monkeypatch.setattr(collection_api, "CollectionRepository", FakeRepository)

    result = asyncio.run(collection_api.get_collection_status(None, None))

    assert result.enabled is True
    assert result.running is False
    assert result.next_run_at is not None
    assert result.last_run is not None
    assert result.last_run.collection_run_id == 5
    assert result.consecutive_failures == 2


def test_missing_collection_run_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_run(self, _run_id: int) -> None:
            return None

    monkeypatch.setattr(collection_api, "CollectionRepository", FakeRepository)

    with pytest.raises(HTTPException) as error:
        asyncio.run(collection_api.get_collection_run(999, None, None))

    assert error.value.status_code == status.HTTP_404_NOT_FOUND


def test_history_error_message_masks_tokens() -> None:
    message = safe_error_message(
        RuntimeError("request failed: access_token=very-secret&v=5.199")
    )

    assert "very-secret" not in message
    assert "access_token=***" in message
