import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

import news_reposter.services.scheduler as scheduler_module
from news_reposter.config import Settings
from news_reposter.services.scheduler import CollectionScheduler


def make_scheduler(**overrides: object) -> CollectionScheduler:
    values: dict[str, object] = {
        "collection_enabled": True,
        "collection_interval_minutes": 15,
        "collection_start_hour": 8,
        "collection_end_hour": 20,
        "collection_timezone": "Europe/Moscow",
    }
    values.update(overrides)
    settings = Settings(_env_file=None, **values)
    return CollectionScheduler(settings)


def test_collection_schedule_defaults() -> None:
    """Проверяет базовое расписание MVP: каждые 15 минут с 08:00 до 20:00."""

    settings = Settings(_env_file=None)

    assert settings.collection_enabled is True
    assert settings.collection_interval_minutes == 15
    assert settings.collection_start_hour == 8
    assert settings.collection_end_hour == 20
    assert settings.collection_timezone == "Europe/Moscow"


def test_next_run_aligns_to_interval() -> None:
    """Планировщик выравнивает запуск по сетке 08:00, 08:15, 08:30 и т.д."""

    tz = ZoneInfo("Europe/Moscow")
    scheduler = make_scheduler()

    assert scheduler.next_run_at(datetime(2026, 9, 11, 7, 50, tzinfo=tz)) == datetime(
        2026, 9, 11, 8, 0, tzinfo=tz
    )
    assert scheduler.next_run_at(datetime(2026, 9, 11, 8, 7, tzinfo=tz)) == datetime(
        2026, 9, 11, 8, 15, tzinfo=tz
    )
    assert scheduler.next_run_at(datetime(2026, 9, 11, 19, 46, tzinfo=tz)) == datetime(
        2026, 9, 12, 8, 0, tzinfo=tz
    )


def test_schedule_can_be_configured() -> None:
    """Проверяет изменение интервала и рабочего окна."""

    tz = ZoneInfo("Europe/Moscow")
    scheduler = make_scheduler(
        collection_interval_minutes=30,
        collection_start_hour=9,
        collection_end_hour=18,
    )

    assert scheduler.next_run_at(datetime(2026, 9, 11, 9, 1, tzinfo=tz)) == datetime(
        2026, 9, 11, 9, 30, tzinfo=tz
    )


def test_scheduler_run_once_collects_all_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Плановый запуск вызывает основной сборщик и возвращает его сводку."""

    expected = {
        "sources_checked": 2,
        "posts_created": 10,
        "queue_items_created": 10,
        "errors": 0,
    }
    calls = 0

    async def fake_collect() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return expected

    monkeypatch.setattr(scheduler_module, "collect_active_sources_once", fake_collect)

    result = asyncio.run(make_scheduler().run_once())

    assert result == expected
    assert calls == 1


def test_invalid_collection_window_is_rejected() -> None:
    """Ошибочное окно расписания обнаруживается при запуске приложения."""

    with pytest.raises(ValidationError, match="COLLECTION_END_HOUR"):
        Settings(
            _env_file=None,
            collection_start_hour=20,
            collection_end_hour=8,
        )
