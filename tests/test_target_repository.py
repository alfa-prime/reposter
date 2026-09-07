import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Target
from news_reposter.repositories import TargetAlreadyExistsError, TargetRepository
from news_reposter.schemas import TargetCreate, TargetUpdate


def test_target_repository_creates_target() -> None:
    """Проверяет сохранение новой цели публикации."""

    async def scenario() -> None:
        """Создаёт цель через репозиторий."""

        session = AsyncMock(spec=AsyncSession)
        repository = TargetRepository(session)
        data = TargetCreate(
            name="Новости 51 региона",
            platform="max",
            external_id="-77162942582085",
        )

        target = await repository.create(data)

        assert target.external_id == "-77162942582085"
        assert target.is_active is True
        session.add.assert_called_once_with(target)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(target)

    asyncio.run(scenario())


def test_target_repository_rolls_back_duplicate() -> None:
    """Проверяет откат транзакции при повторной цели."""

    async def scenario() -> None:
        """Имитирует нарушение составной уникальности."""

        session = AsyncMock(spec=AsyncSession)
        session.commit.side_effect = IntegrityError(
            statement="INSERT INTO targets",
            params={},
            orig=Exception("duplicate"),
        )
        repository = TargetRepository(session)
        data = TargetCreate(
            name="Дубль",
            platform="max",
            external_id="-77162942582085",
        )

        with pytest.raises(TargetAlreadyExistsError):
            await repository.create(data)

        session.rollback.assert_awaited_once()
        session.refresh.assert_not_awaited()

    asyncio.run(scenario())


def test_target_repository_filters_and_updates_targets() -> None:
    """Проверяет фильтрацию и изменение цели публикации."""

    async def scenario() -> None:
        """Формирует выборку и изменяет подготовленную запись."""

        session = AsyncMock(spec=AsyncSession)
        result = Mock()
        target = Target(
            target_id=1,
            name="Канал",
            platform="max",
            external_id="-1",
        )
        result.all.return_value = [target]
        session.scalars.return_value = result
        repository = TargetRepository(session)

        targets = await repository.list(
            offset=0,
            limit=10,
            platform="max",
            is_active=True,
        )
        updated = await repository.update(
            target,
            TargetUpdate(name="Новое название", url=None),
        )

        assert targets == [target]
        statement = session.scalars.await_args.args[0]
        assert "targets.platform" in str(statement)
        assert "targets.is_active" in str(statement)
        assert updated.name == "Новое название"
        assert updated.url is None
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(target)

    asyncio.run(scenario())
