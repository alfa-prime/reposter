import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.config import Settings
from news_reposter.db.base import Base
from news_reposter.db.session import async_session_factory, engine


def test_database_uses_asyncpg_driver() -> None:
    """Проверяет использование асинхронного драйвера PostgreSQL."""

    assert engine.url.drivername == "postgresql+asyncpg"


def test_session_factory_creates_async_session() -> None:
    """Проверяет создание асинхронной SQLAlchemy-сессии."""

    async def scenario() -> None:
        """Создаёт и закрывает сессию без обращения к базе."""

        async with async_session_factory() as session:
            assert isinstance(session, AsyncSession)

    asyncio.run(scenario())


def test_database_settings_can_be_overridden() -> None:
    """Проверяет настройку подключения через переменные окружения."""

    settings = Settings(
        postgres_user="user",
        postgres_password="p@ss:word",
        postgres_host="database",
        postgres_port=5433,
        postgres_db="test_db",
        database_echo=True,
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:p%40ss%3Aword@database:5433/test_db"
    )
    assert settings.database_echo is True


def test_constraint_naming_convention_is_configured() -> None:
    """Проверяет стабильные имена ограничений для будущих миграций."""

    assert Base.metadata.naming_convention is not None
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
