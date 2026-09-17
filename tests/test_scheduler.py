import asyncio
from datetime import datetime, time
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import httpx
import pytest

import news_reposter.services.scheduler as scheduler_module
from news_reposter.db.models import CollectionRunTrigger
from news_reposter.services.scheduler import (
    CollectionSchedule,
    CollectionScheduler,
    next_run_at,
)


def make_schedule(**overrides: object) -> CollectionSchedule:
    values: dict[str, object] = {
        "enabled": True,
        "interval_minutes": 15,
        "start_time": time(8),
        "end_time": time(20),
        "timezone": "Europe/Moscow",
    }
    values.update(overrides)
    return CollectionSchedule(**values)  # type: ignore[arg-type]


def test_next_run_aligns_to_interval() -> None:
    tz = ZoneInfo("Europe/Moscow")
    schedule = make_schedule()

    assert next_run_at(datetime(2026, 9, 11, 7, 50, tzinfo=tz), schedule) == datetime(
        2026, 9, 11, 8, 0, tzinfo=tz
    )
    assert next_run_at(datetime(2026, 9, 11, 8, 7, tzinfo=tz), schedule) == datetime(
        2026, 9, 11, 8, 15, tzinfo=tz
    )
    assert next_run_at(datetime(2026, 9, 11, 19, 46, tzinfo=tz), schedule) == datetime(
        2026, 9, 12, 8, 0, tzinfo=tz
    )


def test_overnight_schedule_runs_across_midnight() -> None:
    tz = ZoneInfo("Europe/Moscow")
    schedule = make_schedule(start_time=time(20), end_time=time(8), interval_minutes=30)

    assert next_run_at(datetime(2026, 9, 11, 19, 0, tzinfo=tz), schedule) == datetime(
        2026, 9, 11, 20, 0, tzinfo=tz
    )
    assert next_run_at(datetime(2026, 9, 11, 23, 11, tzinfo=tz), schedule) == datetime(
        2026, 9, 11, 23, 30, tzinfo=tz
    )
    assert next_run_at(datetime(2026, 9, 12, 1, 11, tzinfo=tz), schedule) == datetime(
        2026, 9, 12, 1, 30, tzinfo=tz
    )
    assert next_run_at(datetime(2026, 9, 12, 8, 0, tzinfo=tz), schedule) == datetime(
        2026, 9, 12, 20, 0, tzinfo=tz
    )


def test_equal_window_boundaries_are_rejected() -> None:
    tz = ZoneInfo("Europe/Moscow")
    with pytest.raises(ValueError, match="не должны совпадать"):
        next_run_at(
            datetime(2026, 9, 11, 8, tzinfo=tz),
            make_schedule(start_time=time(8), end_time=time(8)),
        )


def test_scheduler_run_once_marks_scheduled_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "run_id": 1,
        "sources_total": 2,
        "sources_checked": 2,
        "sources_succeeded": 2,
        "posts_found": 10,
        "posts_created": 10,
        "queue_items_created": 10,
        "errors": 0,
    }
    triggers: list[CollectionRunTrigger] = []
    http_client = Mock(spec=httpx.AsyncClient)

    async def fake_collect(
        client: object,
        trigger: CollectionRunTrigger,
    ) -> dict[str, int]:
        assert client is http_client
        triggers.append(trigger)
        return expected

    monkeypatch.setattr(scheduler_module, "collect_active_sources_once", fake_collect)

    result = asyncio.run(CollectionScheduler(http_client).run_once())

    assert result == expected
    assert triggers == [CollectionRunTrigger.SCHEDULED]
