import asyncio
import base64
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from news_reposter.api.dependencies import get_avatar_service, get_current_auth
from news_reposter.auth.session_tokens import hash_token
from news_reposter.config import get_settings
from news_reposter.db.models import Role, User
from news_reposter.main import app
from news_reposter.services.avatars import AvatarFile

CSRF_TOKEN = "avatar-csrf-token"
CSRF_COOKIE_NAME = get_settings().auth_csrf_cookie_name
PNG = b"\x89PNG\r\n\x1a\n" + b"avatar-data"


@pytest.fixture
def avatar_api(tmp_path: Path) -> Iterator[AsyncMock]:
    role = Role(code="viewer", name="Наблюдатель", is_active=True, permissions=[])
    user = User(
        user_id=1,
        username="admin",
        username_normalized="admin",
        display_name="Администратор",
        password_hash="hash",
        is_active=True,
        must_change_password=False,
        roles=[role],
    )
    auth = SimpleNamespace(
        user=user,
        session=SimpleNamespace(csrf_token_hash=hash_token(CSRF_TOKEN)),
        role_codes=frozenset({"viewer"}),
        permission_codes=frozenset(),
    )
    avatar_path = tmp_path / "avatar.png"
    avatar_path.write_bytes(PNG)
    service = AsyncMock()

    async def replace(_user_id: int, **_data: object) -> User:
        user.avatar_storage_key = "avatars/1/avatar.png"
        user.avatar_updated_at = datetime.now(UTC)
        return user

    async def delete(_user_id: int) -> User:
        user.avatar_storage_key = None
        user.avatar_updated_at = datetime.now(UTC)
        return user

    service.replace.side_effect = replace
    service.delete.side_effect = delete
    service.find.return_value = AvatarFile(avatar_path, "image/png")
    app.dependency_overrides[get_current_auth] = lambda: auth
    app.dependency_overrides[get_avatar_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_current_auth, None)
        app.dependency_overrides.pop(get_avatar_service, None)


def test_avatar_upload_download_and_delete(avatar_api: AsyncMock) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
        ) as client:
            uploaded = await client.post(
                "/api/v1/auth/avatar",
                json={
                    "filename": "avatar.png",
                    "content_type": "image/png",
                    "data_base64": base64.b64encode(PNG).decode(),
                },
            )
            downloaded = await client.get("/api/v1/auth/avatars/1")
            deleted = await client.delete("/api/v1/auth/avatar")

        assert uploaded.status_code == 200
        assert uploaded.json()["avatar_url"].startswith("/api/v1/auth/avatars/1?v=")
        assert downloaded.status_code == 200
        assert downloaded.content == PNG
        assert downloaded.headers["cache-control"] == (
            "private, max-age=31536000, immutable"
        )
        assert deleted.status_code == 200
        assert deleted.json()["avatar_url"] is None

    asyncio.run(scenario())
    avatar_api.replace.assert_awaited_once()
    avatar_api.find.assert_awaited_once_with(1)
    avatar_api.delete.assert_awaited_once_with(1)


def test_avatar_upload_requires_valid_base64(avatar_api: AsyncMock) -> None:
    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://test",
            cookies={CSRF_COOKIE_NAME: CSRF_TOKEN},
            headers={"X-CSRF-Token": CSRF_TOKEN},
        ) as client:
            response = await client.post(
                "/api/v1/auth/avatar",
                json={
                    "filename": "avatar.png",
                    "content_type": "image/png",
                    "data_base64": "not-base64!",
                },
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Некорректные данные изображения"}

    asyncio.run(scenario())
    avatar_api.replace.assert_not_awaited()
