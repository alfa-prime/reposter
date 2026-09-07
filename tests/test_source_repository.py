import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Source
from news_reposter.repositories import SourceAlreadyExistsError, SourceRepository
from news_reposter.schemas import SourceCreate, SourceUpdate


def test_repository_creates_source() -> None:
    """Проверяет сохранение нового источника в транзакции."""

    async def scenario() -> None:
        """Создаёт источник через репозиторий."""

        session = AsyncMock(spec=AsyncSession)
        repository = SourceRepository(session)
        data = SourceCreate(
            name="Полуостров 51",
            platform="vk",
            url="https://vk.ru/peninsula51",
        )

        source = await repository.create(data)

        assert source.name == "Полуостров 51"
        assert source.is_active is True
        session.add.assert_called_once_with(source)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(source)

    asyncio.run(scenario())


def test_repository_rolls_back_duplicate() -> None:
    """Проверяет откат транзакции при повторной ссылке."""

    async def scenario() -> None:
        """Имитирует нарушение уникальности в PostgreSQL."""

        session = AsyncMock(spec=AsyncSession)
        session.commit.side_effect = IntegrityError(
            statement="INSERT INTO sources",
            params={},
            orig=Exception("duplicate"),
        )
        repository = SourceRepository(session)
        data = SourceCreate(
            name="Дубль",
            platform="vk",
            url="https://vk.ru/peninsula51",
        )

        with pytest.raises(SourceAlreadyExistsError):
            await repository.create(data)

        session.rollback.assert_awaited_once()
        session.refresh.assert_not_awaited()

    asyncio.run(scenario())


def test_repository_filters_sources() -> None:
    """Проверяет формирование выборки с фильтрами и пагинацией."""

    async def scenario() -> None:
        """Получает список через подготовленный результат SQLAlchemy."""

        session = AsyncMock(spec=AsyncSession)
        result = Mock()
        result.all.return_value = [
            Source(
                id=2,
                name="Лента",
                platform="rss",
                url="https://example.com/feed",
            )
        ]
        session.scalars.return_value = result

        sources = await SourceRepository(session).list(
            offset=10,
            limit=20,
            platform="rss",
            is_active=True,
        )

        assert len(sources) == 1
        statement = session.scalars.await_args.args[0]
        sql = str(statement)
        assert "sources.platform" in sql
        assert "sources.is_active" in sql
        assert "LIMIT" in sql
        assert "OFFSET" in sql

    asyncio.run(scenario())


def test_repository_updates_and_deletes_source() -> None:
    """Проверяет изменение и удаление существующего источника."""

    async def scenario() -> None:
        """Выполняет две изменяющие операции через одну сессию."""

        session = AsyncMock(spec=AsyncSession)
        repository = SourceRepository(session)
        source = Source(
            id=1,
            name="Старое название",
            platform="vk",
            url="https://vk.ru/source",
            is_active=True,
        )

        updated = await repository.update(
            source,
            SourceUpdate(name="Новое название", is_active=False),
        )
        await repository.delete(updated)

        assert updated.name == "Новое название"
        assert updated.is_active is False
        assert session.commit.await_count == 2
        session.refresh.assert_awaited_once_with(updated)
        session.delete.assert_awaited_once_with(updated)

    asyncio.run(scenario())
