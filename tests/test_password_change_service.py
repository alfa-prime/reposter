import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from news_reposter.auth.passwords import PasswordValidationError
from news_reposter.auth.session_tokens import SessionTokens, hash_token
from news_reposter.db.models import User, UserSession
from news_reposter.services.password_change import (
    CurrentPasswordInvalidError,
    PasswordChangeService,
    PasswordChangeUserUnavailableError,
    PasswordUnchangedError,
)
from news_reposter.services.user_sessions import CreatedSession

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class MemoryUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.lookup: int | None = None

    async def get_by_id_for_update(self, user_id: int) -> User | None:
        self.lookup = user_id
        return self.user


def make_user(*, is_active: bool = True) -> User:
    return User(
        user_id=7,
        username="admin",
        username_normalized="admin",
        display_name="Administrator",
        password_hash="$argon2id$old",
        is_active=is_active,
        must_change_password=True,
    )


def created_session() -> CreatedSession:
    session = UserSession(
        session_id=31,
        user_id=7,
        token_hash=hash_token("new-session-token"),
        csrf_token_hash=hash_token("new-csrf-token"),
        created_at=NOW,
        last_seen_at=NOW,
        absolute_expires_at=NOW + timedelta(hours=12),
    )
    return CreatedSession(
        session=session,
        tokens=SessionTokens(
            session_token="new-session-token",
            csrf_token="new-csrf-token",
        ),
    )


def make_service(
    user: User | None,
) -> tuple[PasswordChangeService, AsyncMock, Mock, AsyncMock, MemoryUserRepository]:
    db = AsyncMock()
    passwords = Mock()
    sessions = AsyncMock()
    sessions.replace_after_password_change.return_value = created_session()
    users = MemoryUserRepository(user)
    service = PasswordChangeService(
        db,
        password_manager=passwords,
        user_repository=users,
        session_service=sessions,
    )
    return service, db, passwords, sessions, users


def test_change_password_updates_hash_and_rotates_sessions() -> None:
    async def scenario() -> None:
        user = make_user()
        service, db, passwords, sessions, users = make_service(user)
        passwords.verify.return_value = True
        passwords.hash.return_value = "$argon2id$new"

        result = await service.change(
            user_id=7,
            current_password="old secure password",
            new_password="new secure password",
            client_ip="192.0.2.25",
            user_agent="test-browser",
            now=NOW,
        )

        assert users.lookup == 7
        assert result.user is user
        assert (
            result.created_session
            is sessions.replace_after_password_change.return_value
        )
        assert user.password_hash == "$argon2id$new"
        assert user.must_change_password is False
        passwords.verify.assert_called_once_with(
            "old secure password",
            "$argon2id$old",
        )
        passwords.hash.assert_called_once_with("new secure password")
        sessions.replace_after_password_change.assert_awaited_once_with(
            user,
            client_ip="192.0.2.25",
            user_agent="test-browser",
            now=NOW,
        )
        db.rollback.assert_not_awaited()

    asyncio.run(scenario())


def test_change_password_rejects_wrong_current_password() -> None:
    async def scenario() -> None:
        user = make_user()
        service, db, passwords, sessions, _ = make_service(user)
        passwords.verify.return_value = False

        with pytest.raises(CurrentPasswordInvalidError):
            await service.change(
                user_id=7,
                current_password="wrong password",
                new_password="new secure password",
            )

        assert user.password_hash == "$argon2id$old"
        assert user.must_change_password is True
        passwords.hash.assert_not_called()
        sessions.replace_after_password_change.assert_not_awaited()
        db.rollback.assert_awaited_once()

    asyncio.run(scenario())


def test_change_password_rejects_same_password() -> None:
    async def scenario() -> None:
        service, db, passwords, sessions, _ = make_service(make_user())
        passwords.verify.return_value = True

        with pytest.raises(PasswordUnchangedError):
            await service.change(
                user_id=7,
                current_password="same secure password",
                new_password="same secure password",
            )

        passwords.hash.assert_not_called()
        sessions.replace_after_password_change.assert_not_awaited()
        db.rollback.assert_awaited_once()

    asyncio.run(scenario())


def test_change_password_rolls_back_policy_failure() -> None:
    async def scenario() -> None:
        user = make_user()
        service, db, passwords, sessions, _ = make_service(user)
        passwords.verify.return_value = True
        passwords.hash.side_effect = PasswordValidationError("too short")

        with pytest.raises(PasswordValidationError, match="too short"):
            await service.change(
                user_id=7,
                current_password="old secure password",
                new_password="short",
            )

        assert user.password_hash == "$argon2id$old"
        assert user.must_change_password is True
        sessions.replace_after_password_change.assert_not_awaited()
        db.rollback.assert_awaited_once()

    asyncio.run(scenario())


def test_change_password_rolls_back_session_replacement_failure() -> None:
    async def scenario() -> None:
        user = make_user()
        service, db, passwords, sessions, _ = make_service(user)
        passwords.verify.return_value = True
        passwords.hash.return_value = "$argon2id$new"
        sessions.replace_after_password_change.side_effect = RuntimeError(
            "database unavailable"
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            await service.change(
                user_id=7,
                current_password="old secure password",
                new_password="new secure password",
            )

        db.rollback.assert_awaited_once()

    asyncio.run(scenario())


@pytest.mark.parametrize("user", [None, make_user(is_active=False)])
def test_change_password_rejects_missing_or_inactive_user(user: User | None) -> None:
    async def scenario() -> None:
        service, db, passwords, sessions, _ = make_service(user)

        with pytest.raises(PasswordChangeUserUnavailableError):
            await service.change(
                user_id=7,
                current_password="old secure password",
                new_password="new secure password",
            )

        passwords.verify.assert_not_called()
        sessions.replace_after_password_change.assert_not_awaited()
        db.rollback.assert_awaited_once()

    asyncio.run(scenario())
