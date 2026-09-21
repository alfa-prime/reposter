import asyncio
from unittest.mock import AsyncMock

from sqlalchemy import BigInteger
from sqlalchemy.dialects import postgresql

from news_reposter.db.models import User
from news_reposter.repositories.login_attempt import LoginAttemptRepository
from news_reposter.repositories.user import UserRepository
from news_reposter.repositories.user_session import UserSessionRepository


def test_rate_limit_locks_are_unique_ordered_bigints() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        repository = LoginAttemptRepository(db)

        await repository.acquire_rate_limit_locks([5, -7, 5])

        assert db.execute.await_count == 2
        statements = [call.args[0] for call in db.execute.await_args_list]
        compiled = [
            statement.compile(dialect=postgresql.dialect()) for statement in statements
        ]
        assert [next(iter(item.params.values())) for item in compiled] == [-7, 5]
        assert all(
            any(isinstance(bind.type, BigInteger) for bind in item.binds.values())
            for item in compiled
        )

    asyncio.run(scenario())


def test_user_lock_refreshes_cached_state_before_session_creation() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        expected = User(user_id=7, is_active=False)
        db.scalar.return_value = expected
        repository = UserSessionRepository(db)

        result = await repository.lock_user(7)

        assert result is expected
        statement = db.scalar.await_args.args[0]
        assert statement.get_execution_options()["populate_existing"] is True
        assert statement._for_update_arg is not None

    asyncio.run(scenario())


def test_authentication_user_lookup_locks_and_refreshes_user() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        expected = User(user_id=7, is_active=True)
        db.scalar.return_value = expected
        repository = UserRepository(db)

        result = await repository.get_by_normalized_username_for_update("admin")

        assert result is expected
        statement = db.scalar.await_args.args[0]
        assert statement.get_execution_options()["populate_existing"] is True
        assert statement._for_update_arg is not None

    asyncio.run(scenario())


def test_password_change_user_lookup_locks_and_refreshes_user() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        expected = User(user_id=7, is_active=True)
        db.scalar.return_value = expected
        repository = UserRepository(db)

        result = await repository.get_by_id_for_update(7)

        assert result is expected
        statement = db.scalar.await_args.args[0]
        assert statement.get_execution_options()["populate_existing"] is True
        assert statement._for_update_arg is not None

    asyncio.run(scenario())
