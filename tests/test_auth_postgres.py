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
            assert persisted_session.ip_address == "192.0.2.10"
            assert persisted_attempt is not None
            assert persisted_attempt.user_id == user_id
            assert persisted_attempt.was_successful is True
            assert persisted_attempt.request_id == request_id

    asyncio.run(scenario())
