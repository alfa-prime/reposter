import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from news_reposter.db.models import User
from news_reposter.services.avatars import (
    MAX_AVATAR_BYTES,
    AvatarService,
    AvatarTooLargeError,
    AvatarValidationError,
    avatar_url,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"avatar-data"


class MemoryUserRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.user_id == user_id else None

    async def get_by_id_for_update(self, user_id: int) -> User | None:
        return await self.get_by_id(user_id)


def make_user() -> User:
    return User(
        user_id=7,
        username="editor",
        username_normalized="editor",
        display_name="Редактор",
        password_hash="hash",
        is_active=True,
        roles=[],
    )


def test_avatar_service_replaces_and_deletes_file(tmp_path: Path) -> None:
    async def scenario() -> None:
        user = make_user()
        old_path = tmp_path / "avatars" / "7" / "old.png"
        old_path.parent.mkdir(parents=True)
        old_path.write_bytes(PNG)
        user.avatar_storage_key = "avatars/7/old.png"
        session = AsyncMock()
        service = AvatarService(
            session,
            media_root=tmp_path,
            user_repository=MemoryUserRepository(user),
        )

        updated = await service.replace(
            user.user_id,
            content=PNG,
            content_type="image/png",
        )

        assert updated is user
        assert user.avatar_storage_key is not None
        assert user.avatar_storage_key.endswith(".png")
        assert user.avatar_updated_at is not None
        assert not old_path.exists()
        stored = tmp_path / user.avatar_storage_key
        assert stored.read_bytes() == PNG
        assert avatar_url(user).startswith("/api/v1/auth/avatars/7?v=")

        found = await service.find(user.user_id)
        assert found is not None
        assert found.path == stored
        assert found.media_type == "image/png"

        deleted = await service.delete(user.user_id)
        assert deleted.avatar_storage_key is None
        assert not stored.exists()
        assert avatar_url(deleted) is None
        assert session.commit.await_count == 2

    asyncio.run(scenario())


def test_avatar_service_rejects_oversized_and_fake_images(tmp_path: Path) -> None:
    async def scenario() -> None:
        user = make_user()
        session = AsyncMock()
        service = AvatarService(
            session,
            media_root=tmp_path,
            user_repository=MemoryUserRepository(user),
        )

        with pytest.raises(AvatarTooLargeError, match="5 МБ"):
            await service.replace(
                user.user_id,
                content=b"x" * (MAX_AVATAR_BYTES + 1),
                content_type="image/png",
            )
        with pytest.raises(AvatarValidationError, match="не похоже"):
            await service.replace(
                user.user_id,
                content=b"not-an-image",
                content_type="image/png",
            )

        session.commit.assert_not_awaited()

    asyncio.run(scenario())
