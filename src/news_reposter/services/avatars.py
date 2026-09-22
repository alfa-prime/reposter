"""Хранение пользовательских аватаров в общем media volume."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.models import User
from news_reposter.repositories.user import UserRepository
from news_reposter.services.media_storage import MEDIA_ROOT
from news_reposter.services.media_validation import (
    MediaValidationError,
    validate_image_content,
)

MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
AVATAR_MEDIA_TYPES = {
    extension: media_type for media_type, extension in AVATAR_TYPES.items()
}


class AvatarValidationError(ValueError):
    """Файл не подходит для использования в качестве аватара."""


class AvatarTooLargeError(AvatarValidationError):
    """Размер изображения превышает установленный предел."""


class AvatarUserUnavailableError(RuntimeError):
    """Пользователь исчез или был отключён во время запроса."""


@dataclass(frozen=True, slots=True)
class AvatarFile:
    """Проверенный путь к сохранённому аватару и его MIME-тип."""

    path: Path
    media_type: str


def avatar_url(user: User) -> str | None:
    """Возвращает URL аватара с версией для сброса браузерного кеша."""

    if not user.avatar_storage_key:
        return None
    version = (
        int(user.avatar_updated_at.timestamp() * 1_000_000)
        if user.avatar_updated_at is not None
        else 0
    )
    return f"/api/v1/auth/avatars/{user.user_id}?v={version}"


class AvatarService:
    """Атомарно связывает профиль с файлом аватара."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        media_root: Path | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.session = session
        self.media_root = media_root or MEDIA_ROOT
        self.users = user_repository or UserRepository(session)

    async def replace(
        self,
        user_id: int,
        *,
        content: bytes,
        content_type: str,
    ) -> User:
        """Проверяет, сохраняет новый аватар и удаляет прежний файл."""

        if not content:
            raise AvatarValidationError("Файл изображения пуст")
        if len(content) > MAX_AVATAR_BYTES:
            raise AvatarTooLargeError("Размер аватара не должен превышать 5 МБ")

        declared_type = content_type.lower()
        extension = AVATAR_TYPES.get(declared_type)
        if extension is None:
            raise AvatarValidationError("Поддерживаются изображения JPEG, PNG и WebP")
        try:
            validate_image_content(content, declared_type)
        except MediaValidationError as exc:
            raise AvatarValidationError(str(exc)) from exc

        user = await self.users.get_by_id_for_update(user_id)
        if user is None or not user.is_active:
            await self.session.rollback()
            raise AvatarUserUnavailableError("Пользователь не найден или отключён")

        relative_path = (
            Path("avatars") / str(user_id) / f"avatar-{uuid4().hex}{extension}"
        )
        target = self.media_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        previous_key = user.avatar_storage_key
        user.avatar_storage_key = relative_path.as_posix()
        user.avatar_updated_at = datetime.now(UTC)

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            target.unlink(missing_ok=True)
            raise

        self._delete_storage_key(previous_key)
        return user

    async def delete(self, user_id: int) -> User:
        """Удаляет аватар пользователя, если он был установлен."""

        user = await self.users.get_by_id_for_update(user_id)
        if user is None or not user.is_active:
            await self.session.rollback()
            raise AvatarUserUnavailableError("Пользователь не найден или отключён")

        previous_key = user.avatar_storage_key
        user.avatar_storage_key = None
        user.avatar_updated_at = datetime.now(UTC)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        self._delete_storage_key(previous_key)
        return user

    async def find(self, user_id: int) -> AvatarFile | None:
        """Возвращает существующий файл аватара указанного пользователя."""

        user = await self.users.get_by_id(user_id)
        if user is None or not user.avatar_storage_key:
            return None
        try:
            path = self._safe_path(user.avatar_storage_key)
        except ValueError:
            return None
        media_type = AVATAR_MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None or not path.is_file():
            return None
        return AvatarFile(path=path, media_type=media_type)

    def _delete_storage_key(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        try:
            self._safe_path(storage_key).unlink(missing_ok=True)
        except (OSError, ValueError):
            return

    def _safe_path(self, storage_key: str) -> Path:
        root = self.media_root.resolve()
        candidate = (root / storage_key).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Некорректный путь аватара")
        return candidate


__all__ = [
    "AVATAR_TYPES",
    "MAX_AVATAR_BYTES",
    "AvatarFile",
    "AvatarService",
    "AvatarTooLargeError",
    "AvatarUserUnavailableError",
    "AvatarValidationError",
    "avatar_url",
]
