import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import Settings
from news_reposter.db.models import User, UserSession
from news_reposter.services.user_sessions import (
    InvalidSessionError,
    SessionRevocationReason,
    SessionUserUnavailableError,
    UserSessionService,
)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


class MemorySessionRepository:
    def __init__(
        self,
        *,
        user: User | None = None,
        stored_session: UserSession | None = None,
        usable_sessions: list[UserSession] | None = None,
    ) -> None:
        self.user = user
        self.stored_session = stored_session
        self.usable_sessions = usable_sessions or []
        self.locked_user_id: int | None = None
        self.lookup_hash: bytes | None = None
        self.added: UserSession | None = None
        self.revocations: list[tuple[int, datetime, str]] = []
        self.touch_result = True
        self.touches: list[tuple[int, datetime]] = []
        self.revoke_all_result = 0
        self.revoke_all_arguments: tuple[int, datetime, str, int | None] | None = None

    async def lock_user(self, user_id: int) -> User | None:
        self.locked_user_id = user_id
        return self.user

    async def get_by_token_hash(self, token_hash: bytes) -> UserSession | None:
        self.lookup_hash = token_hash
        return self.stored_session

    async def list_usable_for_user(
        self,
        user_id: int,
        *,
        now: datetime,
        idle_cutoff: datetime,
    ) -> list[UserSession]:
        assert user_id == self.user.user_id
        assert now == NOW
        assert idle_cutoff == NOW - timedelta(minutes=60)
        return self.usable_sessions

    def add(self, user_session: UserSession) -> None:
        self.added = user_session

    async def revoke_session(
        self,
        session_id: int,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> bool:
        self.revocations.append((session_id, revoked_at, reason))
        if (
            self.stored_session is not None
            and self.stored_session.revoked_at is not None
        ):
            return False
        return True

    async def touch_active(
        self,
        session_id: int,
        *,
        now: datetime,
    ) -> bool:
        self.touches.append((session_id, now))
        return self.touch_result

    async def revoke_all_for_user(
        self,
        user_id: int,
        *,
        revoked_at: datetime,
        reason: str,
        except_session_id: int | None = None,
    ) -> int:
        self.revoke_all_arguments = (
            user_id,
            revoked_at,
            reason,
            except_session_id,
        )
        return self.revoke_all_result


def settings(**overrides: int) -> Settings:
    return Settings(_env_file=None, **overrides)


def active_user(*, is_active: bool = True) -> User:
    return User(user_id=7, is_active=is_active)


def stored_session(
    *,
    last_seen_at: datetime = NOW - timedelta(minutes=1),
    absolute_expires_at: datetime = NOW + timedelta(hours=1),
    revoked_at: datetime | None = None,
    user_active: bool = True,
) -> UserSession:
    return UserSession(
        session_id=11,
        user_id=7,
        token_hash=hash_token("session-token"),
        csrf_token_hash=hash_token("csrf-token"),
        created_at=NOW - timedelta(hours=1),
        last_seen_at=last_seen_at,
        absolute_expires_at=absolute_expires_at,
        revoked_at=revoked_at,
        user=active_user(is_active=user_active),
    )


def test_create_stores_only_hashes_and_normalized_metadata() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        repository = MemorySessionRepository(user=active_user())
        service = UserSessionService(db, settings=settings(), repository=repository)

        created = await service.create(
            7,
            client_ip="2001:0db8::1",
            user_agent="x" * 600,
            now=NOW,
        )

        saved = created.session
        assert saved is repository.added
        assert repository.locked_user_id == 7
        assert saved.token_hash == hash_token(created.tokens.session_token)
        assert saved.csrf_token_hash == hash_token(created.tokens.csrf_token)
        assert created.tokens.session_token != created.tokens.csrf_token
        assert saved.created_at == NOW
        assert saved.last_seen_at == NOW
        assert saved.absolute_expires_at == NOW + timedelta(hours=12)
        assert saved.ip_address == "2001:db8::1"
        assert saved.user_agent == "x" * 512
        assert not hasattr(saved, "session_token")
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(saved)
        db.rollback.assert_not_awaited()

    asyncio.run(scenario())


def test_create_revokes_oldest_session_when_limit_is_reached() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        old_sessions = [stored_session() for _ in range(3)]
        for session_id, old_session in enumerate(old_sessions, start=21):
            old_session.session_id = session_id
        repository = MemorySessionRepository(
            user=active_user(),
            usable_sessions=old_sessions,
        )
        service = UserSessionService(
            db,
            settings=settings(auth_max_sessions_per_user=3),
            repository=repository,
        )

        await service.create(7, now=NOW)

        assert repository.revocations == [
            (21, NOW, SessionRevocationReason.SESSION_LIMIT.value)
        ]

    asyncio.run(scenario())


def test_create_rolls_back_when_commit_fails() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        database_error = RuntimeError("database unavailable")
        db.commit.side_effect = database_error
        repository = MemorySessionRepository(user=active_user())
        service = UserSessionService(db, settings=settings(), repository=repository)

        with pytest.raises(RuntimeError) as caught:
            await service.create(7, now=NOW)

        assert caught.value is database_error
        db.rollback.assert_awaited_once()
        db.refresh.assert_not_awaited()

    asyncio.run(scenario())


def test_password_change_replaces_all_sessions_in_one_commit() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        user = active_user()
        repository = MemorySessionRepository(user=user)
        repository.revoke_all_result = 3
        service = UserSessionService(db, settings=settings(), repository=repository)

        created = await service.replace_after_password_change(
            user,
            client_ip="192.0.2.25",
            user_agent="new-browser-session",
            now=NOW,
        )

        assert repository.revoke_all_arguments == (
            7,
            NOW,
            SessionRevocationReason.PASSWORD_CHANGED.value,
            None,
        )
        assert created.session is repository.added
        assert created.session.token_hash == hash_token(created.tokens.session_token)
        assert created.session.csrf_token_hash == hash_token(created.tokens.csrf_token)
        assert created.session.ip_address == "192.0.2.25"
        assert created.session.user_agent == "new-browser-session"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(created.session)

    asyncio.run(scenario())


def test_password_change_session_replacement_rolls_back_on_commit_failure() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        db.commit.side_effect = RuntimeError("database unavailable")
        repository = MemorySessionRepository(user=active_user())
        service = UserSessionService(db, settings=settings(), repository=repository)

        with pytest.raises(RuntimeError, match="database unavailable"):
            await service.replace_after_password_change(active_user(), now=NOW)

        assert repository.revoke_all_arguments is not None
        assert repository.added is not None
        db.rollback.assert_awaited_once()
        db.refresh.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize("user", [None, active_user(is_active=False)])
def test_create_rejects_missing_or_inactive_user(user: User | None) -> None:
    async def scenario() -> None:
        db = AsyncMock()
        repository = MemorySessionRepository(user=user)
        service = UserSessionService(db, settings=settings(), repository=repository)

        with pytest.raises(SessionUserUnavailableError):
            await service.create(7, now=NOW)

        assert repository.added is None
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_validate_returns_active_session_without_unnecessary_write() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        expected = stored_session()
        repository = MemorySessionRepository(stored_session=expected)
        service = UserSessionService(db, settings=settings(), repository=repository)

        result = await service.validate("session-token", now=NOW)

        assert result is expected
        assert repository.lookup_hash == hash_token("session-token")
        assert repository.touches == []
        db.commit.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("session", "reason"),
    [
        (
            stored_session(absolute_expires_at=NOW),
            SessionRevocationReason.ABSOLUTE_TIMEOUT,
        ),
        (
            stored_session(last_seen_at=NOW - timedelta(minutes=60)),
            SessionRevocationReason.IDLE_TIMEOUT,
        ),
        (
            stored_session(user_active=False),
            SessionRevocationReason.USER_INACTIVE,
        ),
    ],
)
def test_validate_rejects_and_marks_invalid_session(
    session: UserSession,
    reason: SessionRevocationReason,
) -> None:
    async def scenario() -> None:
        db = AsyncMock()
        repository = MemorySessionRepository(stored_session=session)
        service = UserSessionService(db, settings=settings(), repository=repository)

        with pytest.raises(InvalidSessionError):
            await service.validate("session-token", now=NOW)

        assert repository.revocations == [(11, NOW, reason.value)]
        db.commit.assert_awaited_once()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "session",
    [None, stored_session(revoked_at=NOW - timedelta(minutes=1))],
)
def test_validate_rejects_unknown_or_revoked_session_without_write(
    session: UserSession | None,
) -> None:
    async def scenario() -> None:
        db = AsyncMock()
        repository = MemorySessionRepository(stored_session=session)
        service = UserSessionService(db, settings=settings(), repository=repository)

        with pytest.raises(InvalidSessionError):
            await service.validate("session-token", now=NOW)

        assert repository.revocations == []
        db.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_validate_touches_session_only_after_configured_interval() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        expected = stored_session(last_seen_at=NOW - timedelta(minutes=5))
        repository = MemorySessionRepository(stored_session=expected)
        service = UserSessionService(db, settings=settings(), repository=repository)

        result = await service.validate("session-token", now=NOW)

        assert result is expected
        assert repository.touches == [(11, NOW)]
        assert result.last_seen_at == NOW
        db.commit.assert_awaited_once()

    asyncio.run(scenario())


def test_validate_rejects_session_revoked_during_touch() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        expected = stored_session(last_seen_at=NOW - timedelta(minutes=5))
        repository = MemorySessionRepository(stored_session=expected)
        repository.touch_result = False
        service = UserSessionService(db, settings=settings(), repository=repository)

        with pytest.raises(InvalidSessionError):
            await service.validate("session-token", now=NOW)

        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_revoke_and_revoke_all_are_committed() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        repository = MemorySessionRepository(stored_session=stored_session())
        repository.revoke_all_result = 4
        service = UserSessionService(db, settings=settings(), repository=repository)

        changed = await service.revoke("session-token", now=NOW)
        count = await service.revoke_all_for_user(
            7,
            except_session_id=11,
            reason=SessionRevocationReason.ADMIN_REVOKED,
            now=NOW,
        )

        assert changed is True
        assert count == 4
        assert repository.revocations == [
            (11, NOW, SessionRevocationReason.LOGOUT.value)
        ]
        assert repository.revoke_all_arguments == (
            7,
            NOW,
            SessionRevocationReason.ADMIN_REVOKED.value,
            11,
        )
        assert db.commit.await_count == 2

    asyncio.run(scenario())
