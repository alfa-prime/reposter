import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import Publication, PublicationStatus, QueueItemStatus
from news_reposter.services import publisher
from news_reposter.services.publisher import PublicationError


def publishable_item(
    publication_status: PublicationStatus = PublicationStatus.PENDING,
) -> SimpleNamespace:
    """Создаёт минимальный объект очереди для unit-тестов публикации."""

    return SimpleNamespace(
        queue_item_id=17,
        target_id=3,
        status=QueueItemStatus.APPROVED,
        scheduled_at=None,
        rewritten_text="Готовая новость",
        signature_text=None,
        error_message=None,
        post=SimpleNamespace(original_text="Исходник", attachments=[]),
        target=SimpleNamespace(
            platform="max",
            is_active=True,
            external_id="-123",
            default_signature=None,
        ),
        publication=Publication(
            queue_item_id=17,
            status=publication_status,
            attempts=0,
        ),
    )


def max_settings() -> SimpleNamespace:
    return SimpleNamespace(
        max_access_token="secret",
        max_api_url="https://platform-api.max.ru",
    )


def test_loaded_item_uses_row_lock_for_publication_claim() -> None:
    """Захват публикации блокирует строку QueueItem до смены статуса."""

    async def scenario() -> None:
        session = AsyncMock(spec=AsyncSession)
        session.scalar.return_value = None

        await publisher._loaded_item(session, 17, for_update=True)

        statement = session.scalar.await_args.args[0]
        assert "FOR UPDATE" in str(statement)

    asyncio.run(scenario())


def test_publish_rejects_item_already_claimed_by_another_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Второй конкурентный запуск не делает запрос в MAX."""

    async def scenario() -> None:
        item = publishable_item(PublicationStatus.PUBLISHING)
        session = AsyncMock(spec=AsyncSession)
        http_client = Mock(spec=httpx.AsyncClient)
        loaded = AsyncMock(return_value=item)
        monkeypatch.setattr(publisher, "_loaded_item", loaded)

        with pytest.raises(PublicationError, match="уже выполняется"):
            await publisher.publish_queue_item(session, item.queue_item_id, http_client)

        session.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_publish_commits_claim_before_calling_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Статус publishing фиксируется до внешнего запроса, затем сохраняется успех."""

    async def scenario() -> None:
        item = publishable_item()
        session = AsyncMock(spec=AsyncSession)
        http_client = Mock(spec=httpx.AsyncClient)
        monkeypatch.setattr(
            publisher,
            "_loaded_item",
            AsyncMock(side_effect=[item, item]),
        )
        monkeypatch.setattr(publisher, "get_settings", max_settings)
        max_client_factory = Mock(return_value=SimpleNamespace())
        monkeypatch.setattr(publisher, "MAXClient", max_client_factory)

        async def fake_publish(*_args: object, **_kwargs: object) -> dict[str, object]:
            assert session.commit.await_count == 1
            assert item.publication.status == PublicationStatus.PUBLISHING
            return {"message": {"body": {"mid": "mid-1"}}}

        monkeypatch.setattr(publisher, "_publish_with_media_retry", fake_publish)

        result = await publisher.publish_queue_item(
            session,
            item.queue_item_id,
            http_client,
        )

        assert result is item
        assert session.commit.await_count == 2
        assert item.publication.status == PublicationStatus.PUBLISHED
        assert item.status == QueueItemStatus.PUBLISHED
        assert item.publication.external_message_id == "mid-1"
        max_client_factory.assert_called_once_with(
            access_token="secret",
            http_client=http_client,
            chat_id=-123,
            api_url="https://platform-api.max.ru",
        )

    asyncio.run(scenario())


def test_unexpected_publish_error_releases_claim_as_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Неожиданная ошибка не оставляет публикацию навсегда в publishing."""

    async def scenario() -> None:
        item = publishable_item()
        session = AsyncMock(spec=AsyncSession)
        http_client = Mock(spec=httpx.AsyncClient)
        monkeypatch.setattr(publisher, "_loaded_item", AsyncMock(return_value=item))
        monkeypatch.setattr(publisher, "get_settings", max_settings)
        monkeypatch.setattr(publisher, "MAXClient", lambda **_kwargs: SimpleNamespace())
        monkeypatch.setattr(
            publisher,
            "_publish_with_media_retry",
            AsyncMock(side_effect=RuntimeError("unexpected")),
        )

        with pytest.raises(PublicationError, match="unexpected"):
            await publisher.publish_queue_item(session, item.queue_item_id, http_client)

        assert session.commit.await_count == 2
        assert item.publication.status == PublicationStatus.FAILED
        assert item.status == QueueItemStatus.FAILED
        assert item.error_message == "unexpected"

    asyncio.run(scenario())


def test_publish_can_leave_success_for_atomic_audit_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ручная публикация оставляет успех в транзакции до записи аудита."""

    async def scenario() -> None:
        item = publishable_item()
        session = AsyncMock(spec=AsyncSession)
        http_client = Mock(spec=httpx.AsyncClient)
        monkeypatch.setattr(
            publisher,
            "_loaded_item",
            AsyncMock(side_effect=[item, item]),
        )
        monkeypatch.setattr(publisher, "get_settings", max_settings)
        monkeypatch.setattr(publisher, "MAXClient", lambda **_kwargs: SimpleNamespace())
        monkeypatch.setattr(
            publisher,
            "_publish_with_media_retry",
            AsyncMock(return_value={"message": {"body": {"mid": "mid-1"}}}),
        )

        await publisher.publish_queue_item(
            session,
            item.queue_item_id,
            http_client,
            commit_success=False,
        )

        assert session.commit.await_count == 1
        session.flush.assert_awaited_once()
        assert item.status == QueueItemStatus.PUBLISHED

    asyncio.run(scenario())
