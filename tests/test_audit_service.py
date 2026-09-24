import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from news_reposter.services.audit import record_editorial_event


def test_editorial_event_can_join_existing_transaction() -> None:
    async def scenario() -> None:
        session = SimpleNamespace(
            add=Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )
        item = SimpleNamespace(
            queue_item_id=17,
            post_id=23,
            target_id=5,
            target=SimpleNamespace(name="Редакция"),
        )

        await record_editorial_event(
            session,
            actor_user_id=11,
            item=item,
            action="editorial.deleted",
            commit=False,
        )

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_editorial_event_commits_atomic_operation_by_default() -> None:
    async def scenario() -> None:
        session = SimpleNamespace(
            add=Mock(),
            flush=AsyncMock(),
            commit=AsyncMock(),
        )
        item = SimpleNamespace(
            queue_item_id=17,
            post_id=23,
            target_id=5,
            target=SimpleNamespace(name="Редакция"),
        )

        await record_editorial_event(
            session,
            actor_user_id=11,
            item=item,
            action="editorial.edited",
        )

        session.commit.assert_awaited_once()
        session.flush.assert_not_awaited()

    asyncio.run(scenario())
