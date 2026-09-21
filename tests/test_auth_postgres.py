import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import select

from news_reposter.auth.login_security import username_fingerprint
from news_reposter.auth.passwords import PasswordManager
from news_reposter.db.models import LoginAttempt, User, UserSession
from news_reposter.db.session import async_session_factory
from news_reposter.services.authentication import AuthenticationService
from news_reposter.services.password_change import PasswordChangeService

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires the CI PostgreSQL service",
)


def test_authentication_round_trip_on_postgresql() -> None:
    async def scenario() -> None:
        suffix = uuid4().hex[:12]
        username = f"ci-{suffix}"
        password = "correct horse battery staple"
        request_id = "r" * 64
        manager = PasswordManager()

        async with async_session_factory() as session:
            user = User(
                username=username,
                username_normalized=username,
                display_name="CI authentication user",
                password_hash=manager.hash(password),
                is_active=True,
                must_change_password=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.user_id

            result = await AuthenticationService(
                session,
                password_manager=manager,
            ).authenticate(
                username=username.upper(),
                password=password,
                client_ip="192.0.2.10",
                user_agent="CI browser",
                request_id=request_id,
            )

            assert result.user.user_id == user_id
            assert result.created_session.session.session_id is not None

        async with async_session_factory() as verification_session:
            persisted_user = await verification_session.get(User, user_id)
            persisted_session = await verification_session.scalar(
                select(UserSession).where(UserSession.user_id == user_id)
            )
            persisted_attempt = await verification_session.scalar(
                select(LoginAttempt).where(
                    LoginAttempt.username_fingerprint == username_fingerprint(username)
                )
            )

            assert persisted_user is not None
            assert persisted_user.last_login_at is not None
            assert persisted_session is not None
            assert str(persisted_session.ip_address) == "192.0.2.10"
            assert persisted_attempt is not None
            assert persisted_attempt.user_id == user_id
            assert persisted_attempt.was_successful is True
            assert str(persisted_attempt.ip_address) == "192.0.2.10"
            assert persisted_attempt.request_id == request_id

    asyncio.run(scenario())


def test_password_change_is_atomic_on_postgresql() -> None:
    async def scenario() -> None:
        suffix = uuid4().hex[:12]
        username = f"password-{suffix}"
        old_password = "old correct horse battery staple"
        new_password = "new correct horse battery staple"
        manager = PasswordManager()

        async with async_session_factory() as session:
            user = User(
                username=username,
                username_normalized=username,
                display_name="CI password change user",
                password_hash=manager.hash(old_password),
                is_active=True,
                must_change_password=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.user_id

            login = await AuthenticationService(
                session,
                password_manager=manager,
            ).authenticate(
                username=username,
                password=old_password,
            )
            old_session_id = login.created_session.session.session_id

            changed = await PasswordChangeService(
                session,
                password_manager=manager,
            ).change(
                user_id=user_id,
                current_password=old_password,
                new_password=new_password,
                client_ip="192.0.2.20",
                user_agent="CI password browser",
            )
            new_session_id = changed.created_session.session.session_id

            assert changed.user.must_change_password is False
            assert new_session_id != old_session_id

        async with async_session_factory() as verification_session:
            persisted_user = await verification_session.get(User, user_id)
            sessions = list(
                await verification_session.scalars(
                    select(UserSession)
                    .where(UserSession.user_id == user_id)
                    .order_by(UserSession.session_id)
                )
            )

            assert persisted_user is not None
            assert manager.verify(new_password, persisted_user.password_hash) is True
            assert manager.verify(old_password, persisted_user.password_hash) is False
            assert persisted_user.must_change_password is False
            assert len(sessions) == 2
            assert sessions[0].session_id == old_session_id
            assert sessions[0].revoked_at is not None
            assert sessions[0].revoked_reason == "password_changed"
            assert sessions[1].session_id == new_session_id
            assert sessions[1].revoked_at is None
            assert str(sessions[1].ip_address) == "192.0.2.20"

    asyncio.run(scenario())
