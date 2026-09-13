import base64
import binascii
import os
from pathlib import Path as FilePath
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.db.models import AttachmentType
from news_reposter.db.session import get_db_session
from news_reposter.repositories.queue_item import QueueItemRepository

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
    responses=API_KEY_RESPONSES,
)
Session = Annotated[AsyncSession, Depends(get_db_session)]

MEDIA_ROOT = FilePath(os.getenv("MEDIA_ROOT", "/app/data/media"))
MAX_VIDEO_BYTES = 50 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
VIDEO_EXTENSIONS = set(ALLOWED_VIDEO_TYPES.values())


class QueueVideoUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    data_base64: str = Field(min_length=1)


def media_directory(queue_item_id: int) -> FilePath:
    return MEDIA_ROOT / str(queue_item_id)


def _uploaded_videos(queue_item_id: int) -> list[dict[str, Any]]:
    directory = media_directory(queue_item_id)
    if not directory.exists():
        return []

    result: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        result.append(
            {
                "media_id": path.name,
                "filename": path.name,
                "source_url": f"/api/v1/queue/{queue_item_id}/media/{path.name}",
                "size": path.stat().st_size,
                "kind": "uploaded",
            }
        )
    return result


def _source_videos(item: Any) -> list[dict[str, Any]]:
    post = getattr(item, "post", None)
    if post is None:
        return []

    result: list[dict[str, Any]] = []
    for attachment in getattr(post, "attachments", []):
        if attachment.attachment_type != AttachmentType.VIDEO:
            continue
        raw = attachment.raw_data if isinstance(attachment.raw_data, dict) else {}
        payload = raw.get("video") if isinstance(raw.get("video"), dict) else {}
        title = payload.get("title") if isinstance(payload, dict) else None
        result.append(
            {
                "attachment_id": attachment.attachment_id,
                "external_attachment_id": attachment.external_attachment_id,
                "title": title if isinstance(title, str) and title.strip() else "Видео из VK",
                "source_url": attachment.source_url,
                "kind": "source",
            }
        )
    return result


async def _get_item(queue_item_id: int, session: AsyncSession) -> Any:
    item = await QueueItemRepository(session).get(queue_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")
    return item


@router.get(
    "/{queue_item_id}/video-info",
    summary="Получить сведения о видео публикации",
    description=(
        "Показывает видео, найденные в исходном посте VK, и видео, которые "
        "редактор загрузил вручную. Импорт исходного видео VK пока не выполняется."
    ),
)
async def get_queue_video_info(
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    item = await _get_item(queue_item_id, session)
    source_videos = _source_videos(item)
    uploaded_videos = _uploaded_videos(queue_item_id)
    return {
        "source_video_count": len(source_videos),
        "source_videos": source_videos,
        "uploaded_videos": uploaded_videos,
        "source_video_import_supported": False,
    }


@router.post(
    "/{queue_item_id}/video",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить своё видео к публикации",
    description=(
        "Сохраняет загруженное редактором MP4, WebM или MOV видео. "
        "Максимальный размер одного файла — 50 МБ."
    ),
)
async def upload_queue_video(
    queue_item_id: Annotated[int, Path(gt=0)],
    data: QueueVideoUpload,
    session: Session,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    await _get_item(queue_item_id, session)

    extension = ALLOWED_VIDEO_TYPES.get(data.content_type.lower())
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются MP4, WebM и MOV",
        )

    try:
        content = base64.b64decode(data.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Некорректные данные файла") from exc

    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(content) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Видео больше 50 МБ")

    directory = media_directory(queue_item_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"video-{uuid4().hex}{extension}"
    (directory / filename).write_bytes(content)

    return {
        "media_id": filename,
        "filename": data.filename,
        "source_url": f"/api/v1/queue/{queue_item_id}/media/{filename}",
        "size": len(content),
        "kind": "uploaded",
    }


@router.delete(
    "/{queue_item_id}/video/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить загруженное видео",
)
async def delete_queue_video(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=120)],
    session: Session,
    _api_key: ApiKeyDep,
) -> None:
    await _get_item(queue_item_id, session)
    safe_name = FilePath(media_id).name
    if safe_name != media_id or FilePath(safe_name).suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Некорректное имя видео")

    path = media_directory(queue_item_id) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Видео не найдено")
    path.unlink()
