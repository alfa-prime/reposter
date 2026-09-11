from datetime import datetime
from zoneinfo import ZoneInfo

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
