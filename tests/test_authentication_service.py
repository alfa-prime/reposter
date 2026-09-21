import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from news_reposter.auth.login_security import (
    ip_lock_key,
    username_fingerprint,
    username_lock_key,
)
from news_reposter.config import Settings
from news_reposter.db.models import LoginAttempt, User, UserSession
from news_reposter.services.authentication import (
    AuthenticationService,
    InvalidCredentialsError,
    LoginRateLimitedError,
    _retry_after_seconds,
)
from news_reposter.services.user_sessions import UserSessionService

NOW = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)


class MemoryUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.lookup: str | None = None

    async def get_by_normalized_username(self, username: str) -> User | None:
        self.lookup = username
        return self.user

    async def get_by_normalized_username_for_update(
        self,
        username: str,
    ) -> User | None:
        self.lookup = username
        return self.user


class MemoryAttemptRepository:
    def __init__(self) -> None:
        self.lock_keys: list[int] = []
        self.username_failures: list[datetime] = []
        self.ip_failures: list[datetime] = []
        self.username_query: tuple[bytes, int] | None = None
        self.ip_query: tuple[str, int] | None = None
        self.added: list[LoginAttempt] = []

    async def acquire_rate_limit_locks(self, lock_keys: list[int]) -> None:
        self.lock_keys = lock_keys

    async def recent_failed_by_username(
        self,
        fingerprint: bytes,
        *,
        limit: int,
    ) -> list[datetime]:
        self.username_query = (fingerprint, limit)
        return self.username_failures

    async def recent_failed_by_ip(
        self,
        client_ip: str,
        *,
        limit: int,
    ) -> list[datetime]:
        self.ip_query = (client_ip, limit)
        return self.ip_failures

    def add(self, attempt: LoginAttempt) -> None:
        self.added.append(attempt)


class MemorySessionRepository:
    def __init__(self, user: User) -> None:
        self.user = user
        self.added: UserSession | None = None

    async def lock_user(self, user_id: int) -> User | None:
        assert user_id == self.user.user_id
        return self.user

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
        return []

    async def revoke_session(
        self,
        session_id: int,
        *,
        revoked_at: datetime,
        reason: str,
    ) -> bool:
        raise AssertionError("No session should be revoked")

    def add(self, user_session: UserSession) -> None:
        self.added = user_session


def auth_settings(**overrides: int) -> Settings:
    return Settings(_env_file=None, **overrides)


def make_user(*, is_active: bool = True) -> User:
    return User(
        user_id=7,
        username="Admin",
        username_normalized="admin",
        display_name="Administrator",
        password_hash="$argon2id$old",
        is_active=is_active,
    )


def make_service(
    *,
    user: User | None,
    db: AsyncMock | None = None,
    attempts: MemoryAttemptRepository | None = None,
    passwords: Mock | None = None,
    session_service: object | None = None,
    settings: Settings | None = None,
) -> tuple[
    AuthenticationService,
    AsyncMock,
    MemoryUserRepository,
    MemoryAttemptRepository,
    Mock,
    object,
]:
    database = db or AsyncMock()
    users = MemoryUserRepository(user)
    attempt_repository = attempts or MemoryAttemptRepository()
    password_manager = passwords or Mock()
    sessions = session_service or Mock(create_for_locked_user=AsyncMock())
    service = AuthenticationService(
        database,
        settings=settings or auth_settings(),
        password_manager=password_manager,
        user_repository=users,
        attempt_repository=attempt_repository,
        session_service=sessions,
    )
    return (
        service,
        database,
        users,
        attempt_repository,
        password_manager,
        sessions,
    )


def test_successful_authentication_is_committed_with_new_session() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        user = make_user()
        attempts = MemoryAttemptRepository()
        passwords = Mock()
        passwords.verify_and_update.return_value = (True, "$argon2id$new")
        session_repository = MemorySessionRepository(user)
        session_service = UserSessionService(
            db,
            settings=auth_settings(),
            repository=session_repository,
        )
        service = AuthenticationService(
            db,
            settings=auth_settings(),
            password_manager=passwords,
            user_repository=MemoryUserRepository(user),
            attempt_repository=attempts,
            session_service=session_service,
        )

        result = await service.authenticate(
            username="  ADMIN  ",
            password="correct password",
            client_ip="2001:0db8::1",
            user_agent="test-browser",
            request_id="r" * 64,
            now=NOW,
        )

        assert result.user is user
        assert result.created_session.session is session_repository.added
        assert user.password_hash == "$argon2id$new"
        assert user.last_login_at == NOW
        passwords.verify_and_update.assert_called_once_with(
            "correct password",
            "$argon2id$old",
        )
        passwords.verify_dummy.assert_not_called()

        assert len(attempts.added) == 1
        attempt = attempts.added[0]
        assert attempt.username_fingerprint == username_fingerprint("admin")
        assert attempt.user_id == 7
        assert attempt.ip_address == "2001:db8::1"
        assert attempt.was_successful is True
        assert attempt.attempted_at == NOW
        assert attempt.request_id == "r" * 64
        assert "ADMIN" not in repr(attempt)

        assert set(attempts.lock_keys) == {
            username_lock_key(username_fingerprint("admin")),
            ip_lock_key("2001:db8::1"),
        }
        assert attempts.username_query == (username_fingerprint("admin"), 5)
        assert attempts.ip_query == ("2001:db8::1", 20)
        assert session_repository.added.ip_address == "2001:db8::1"
        assert session_repository.added.user_agent == "test-browser"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(session_repository.added)

    asyncio.run(scenario())


def test_wrong_password_records_generic_failure_without_session() -> None:
    async def scenario() -> None:
        passwords = Mock()
        passwords.verify_and_update.return_value = (False, None)
        service, db, _, attempts, _, sessions = make_service(
            user=make_user(),
            passwords=passwords,
        )

        with pytest.raises(InvalidCredentialsError, match="Неверный логин или пароль"):
            await service.authenticate(
                username="admin",
                password="wrong password",
                client_ip="192.0.2.10",
                now=NOW,
            )

        assert attempts.added[0].user_id == 7
        assert attempts.added[0].was_successful is False
        sessions.create_for_locked_user.assert_not_awaited()
        db.commit.assert_awaited_once()
        db.rollback.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize("username", ["missing-user", " invalid login "])
def test_unknown_or_malformed_username_uses_dummy_argon2(username: str) -> None:
    async def scenario() -> None:
        passwords = Mock()
        service, db, users, attempts, _, sessions = make_service(
            user=None,
            passwords=passwords,
        )

        with pytest.raises(InvalidCredentialsError, match="Неверный логин или пароль"):
            await service.authenticate(
                username=username,
                password="candidate password",
                now=NOW,
            )

        passwords.verify_dummy.assert_called_once_with("candidate password")
        passwords.verify_and_update.assert_not_called()
        if username == " invalid login ":
            assert users.lookup is None
        assert attempts.added[0].user_id is None
        assert attempts.added[0].username_fingerprint == username_fingerprint(username)
        assert not hasattr(attempts.added[0], "username")
        sessions.create_for_locked_user.assert_not_awaited()
        db.commit.assert_awaited_once()

    asyncio.run(scenario())


def test_inactive_user_is_indistinguishable_from_wrong_password() -> None:
    async def scenario() -> None:
        user = make_user(is_active=False)
        passwords = Mock()
        passwords.verify_and_update.return_value = (True, "$argon2id$new")
        service, db, _, attempts, _, sessions = make_service(
            user=user,
            passwords=passwords,
        )

        with pytest.raises(InvalidCredentialsError, match="Неверный логин или пароль"):
            await service.authenticate(
                username="admin",
                password="correct password",
                now=NOW,
            )

        passwords.verify_and_update.assert_called_once()
        assert attempts.added[0].user_id == 7
        assert attempts.added[0].was_successful is False
        assert user.password_hash == "$argon2id$old"
        assert user.last_login_at is None
        sessions.create_for_locked_user.assert_not_awaited()
        db.commit.assert_awaited_once()

    asyncio.run(scenario())


def test_oversized_password_runs_bounded_dummy_check() -> None:
    async def scenario() -> None:
        password = "x" * 2000
        passwords = Mock()
        service, _, _, attempts, _, sessions = make_service(
            user=make_user(),
            passwords=passwords,
        )

        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(
                username="admin",
                password=password,
                now=NOW,
            )

        passwords.verify_dummy.assert_called_once_with("x" * 1024)
        passwords.verify_and_update.assert_not_called()
        assert attempts.added[0].was_successful is False
        sessions.create_for_locked_user.assert_not_awaited()

    asyncio.run(scenario())


def test_untrusted_ip_metadata_is_ignored() -> None:
    async def scenario() -> None:
        passwords = Mock()
        passwords.verify_and_update.return_value = (False, None)
        service, _, _, attempts, _, _ = make_service(
            user=make_user(),
            passwords=passwords,
        )

        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(
                username="admin",
                password="wrong password",
                client_ip="not-an-ip",
                now=NOW,
            )

        assert attempts.added[0].ip_address is None
        assert attempts.ip_query is None
        assert attempts.lock_keys == [username_lock_key(username_fingerprint("admin"))]

    asyncio.run(scenario())


def test_username_limit_rejects_request_without_extending_block() -> None:
    async def scenario() -> None:
        attempts = MemoryAttemptRepository()
        attempts.username_failures = [
            NOW - timedelta(minutes=offset) for offset in range(1, 6)
        ]
        service, db, users, _, passwords, sessions = make_service(
            user=make_user(),
            attempts=attempts,
        )

        with pytest.raises(LoginRateLimitedError) as caught:
            await service.authenticate(
                username="admin",
                password="candidate password",
                client_ip="192.0.2.10",
                now=NOW,
            )

        assert caught.value.retry_after_seconds == 14 * 60
        assert attempts.added == []
        assert users.lookup is None
        passwords.verify_and_update.assert_not_called()
        passwords.verify_dummy.assert_not_called()
        sessions.create_for_locked_user.assert_not_awaited()
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_ip_limit_is_checked_independently() -> None:
    async def scenario() -> None:
        attempts = MemoryAttemptRepository()
        attempts.ip_failures = [
            NOW - timedelta(seconds=offset) for offset in (30, 60, 90)
        ]
        service, db, _, _, _, _ = make_service(
            user=make_user(),
            attempts=attempts,
            settings=auth_settings(auth_login_max_attempts_per_ip=3),
        )

        with pytest.raises(LoginRateLimitedError) as caught:
            await service.authenticate(
                username="admin",
                password="candidate password",
                client_ip="192.0.2.10",
                now=NOW,
            )

        assert caught.value.retry_after_seconds == 14 * 60 + 30
        db.rollback.assert_awaited_once()

    asyncio.run(scenario())


def test_failures_outside_attempt_window_do_not_block() -> None:
    async def scenario() -> None:
        attempts = MemoryAttemptRepository()
        attempts.username_failures = [
            NOW - timedelta(minutes=1),
            NOW - timedelta(minutes=2),
            NOW - timedelta(minutes=3),
            NOW - timedelta(minutes=4),
            NOW - timedelta(minutes=17),
        ]
        passwords = Mock()
        service, db, _, _, _, _ = make_service(
            user=None,
            attempts=attempts,
            passwords=passwords,
        )

        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(
                username="admin",
                password="candidate password",
                now=NOW,
            )

        passwords.verify_dummy.assert_called_once()
        assert len(attempts.added) == 1
        db.commit.assert_awaited_once()
        db.rollback.assert_not_awaited()

    asyncio.run(scenario())


def test_failed_attempt_rolls_back_when_commit_fails() -> None:
    async def scenario() -> None:
        db = AsyncMock()
        database_error = RuntimeError("database unavailable")
        db.commit.side_effect = database_error
        passwords = Mock()
        passwords.verify_and_update.return_value = (False, None)
        service, _, _, _, _, _ = make_service(
            user=make_user(),
            db=db,
            passwords=passwords,
        )

        with pytest.raises(RuntimeError) as caught:
            await service.authenticate(
                username="admin",
                password="wrong password",
                now=NOW,
            )

        assert caught.value is database_error
        db.rollback.assert_awaited_once()

    asyncio.run(scenario())


def test_fingerprint_normalizes_case_width_and_whitespace() -> None:
    assert username_fingerprint("  ＡDMIN  ") == username_fingerprint("admin")
    assert username_lock_key(username_fingerprint("admin")) != ip_lock_key("127.0.0.1")


def test_rate_limit_uses_exact_window_and_block_boundaries() -> None:
    failures = [NOW - timedelta(minutes=offset) for offset in range(1, 6)]

    assert (
        _retry_after_seconds(
            failures,
            threshold=5,
            now=NOW,
            attempt_window=timedelta(minutes=15),
            block_duration=timedelta(minutes=15),
        )
        == 14 * 60
    )
    assert (
        _retry_after_seconds(
            failures,
            threshold=5,
            now=NOW + timedelta(minutes=14),
            attempt_window=timedelta(minutes=15),
            block_duration=timedelta(minutes=15),
        )
        is None
    )
