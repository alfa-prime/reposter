import base64
import binascii
from pathlib import Path as FilePath
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    SameOriginDep,
)
from news_reposter.api.v1.queue_permissions import (
    QueueEditDep,
    QueueReadDep,
    get_accessible_queue_item,
)
from news_reposter.db.models import AttachmentType, QueueItemStatus
from news_reposter.db.session import get_db_session
from news_reposter.repositories.queue_item import QueueItemRepository
from news_reposter.services.media_storage import queue_item_directory
from news_reposter.services.media_validation import (
    MediaValidationError,
    validate_video_content,
)

router = APIRouter(
    prefix="/queue",
    tags=["Очередь постов"],
)
Session = Annotated[AsyncSession, Depends(get_db_session)]

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

    @model_validator(mode="after")
    def validate_real_video_type(self) -> "QueueVideoUpload":
        try:
            content = base64.b64decode(self.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("некорректные Base64-данные видео") from exc
        if not content:
            raise ValueError("пустой видеофайл")
        try:
            validate_video_content(content, self.content_type)
        except MediaValidationError as exc:
            raise ValueError(str(exc)) from exc
        return self


def video_directory(queue_item_id: int) -> FilePath:
    return queue_item_directory(queue_item_id) / "videos"


def _uploaded_videos(queue_item_id: int) -> list[dict[str, Any]]:
    directory = video_directory(queue_item_id)
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
                "source_url": f"/api/v1/queue/{queue_item_id}/video/{path.name}",
                "size": path.stat().st_size,
                "kind": "uploaded",
            }
        )
    return result


def _raw_video_payloads(raw_post: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = raw_post.get("attachments")
    if not isinstance(attachments, list) or not attachments:
        copy_history = raw_post.get("copy_history")
        copied = (
            copy_history[0] if isinstance(copy_history, list) and copy_history else None
        )
        attachments = copied.get("attachments") if isinstance(copied, dict) else []

    result: list[dict[str, Any]] = []
    if not isinstance(attachments, list):
        return result
    for attachment in attachments:
        if not isinstance(attachment, dict) or attachment.get("type") != "video":
            continue
        payload = attachment.get("video")
        if isinstance(payload, dict):
            result.append(payload)
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
                "title": title
                if isinstance(title, str) and title.strip()
                else "Видео из VK",
                "source_url": attachment.source_url,
                "kind": "source",
            }
        )

    if not result and isinstance(getattr(post, "raw_data", None), dict):
        for index, payload in enumerate(_raw_video_payloads(post.raw_data)):
            video_id = payload.get("id")
            owner_id = payload.get("owner_id")
            external_id = None
            if video_id is not None:
                external_id = (
                    str(video_id) if owner_id is None else f"{owner_id}_{video_id}"
                )
            title = payload.get("title")
            player = payload.get("player")
            result.append(
                {
                    "attachment_id": -(index + 1),
                    "external_attachment_id": external_id,
                    "title": title
                    if isinstance(title, str) and title.strip()
                    else "Видео из VK",
                    "source_url": player
                    if isinstance(player, str) and player
                    else None,
                    "kind": "source",
                }
            )
    return result


async def _get_item(
    queue_item_id: int,
    session: AsyncSession,
    auth: Any,
) -> Any:
    item = await get_accessible_queue_item(
        QueueItemRepository(session), queue_item_id, auth
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")
    return item


def _ensure_not_reconciling(item: Any) -> None:
    if item.status == QueueItemStatus.PUBLICATION_UNKNOWN:
        raise HTTPException(
            status_code=409,
            detail="Видео нельзя менять, пока результат публикации не проверен",
        )


@router.get(
    "/{queue_item_id}/video-info",
    summary="Получить сведения о видео публикации",
    description=(
        "Показывает видео, найденные в исходном посте VK, и видео, которые "
        "редактор загрузил вручную. Импорт исходного видео VK пока не выполняется."
    ),
    responses=PERMISSION_AUTH_RESPONSES,
)
async def get_queue_video_info(
    queue_item_id: Annotated[int, Path(gt=0)],
    session: Session,
    auth: QueueReadDep,
) -> dict[str, Any]:
    item = await _get_item(queue_item_id, session, auth)
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
        "Максимальный размер одного файла — 50 МБ. Тип проверяется по содержимому файла."
    ),
    responses=PERMISSION_CSRF_AUTH_RESPONSES,
)
async def upload_queue_video(
    queue_item_id: Annotated[int, Path(gt=0)],
    data: QueueVideoUpload,
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> dict[str, Any]:
    item = await _get_item(queue_item_id, session, auth)
    _ensure_not_reconciling(item)

    extension = ALLOWED_VIDEO_TYPES.get(data.content_type.lower())
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются MP4, WebM и MOV",
        )

    try:
        content = base64.b64decode(data.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail="Некорректные данные файла"
        ) from exc

    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(content) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Видео больше 50 МБ")

    directory = video_directory(queue_item_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"video-{uuid4().hex}{extension}"
    (directory / filename).write_bytes(content)

    return {
        "media_id": filename,
        "filename": data.filename,
        "source_url": f"/api/v1/queue/{queue_item_id}/video/{filename}",
        "size": len(content),
        "kind": "uploaded",
    }


@router.get(
    "/{queue_item_id}/video/{media_id}",
    summary="Получить загруженное видео",
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Видео не найдено"},
    },
)
async def get_queue_video(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=120)],
    session: Session,
    auth: QueueReadDep,
) -> FileResponse:
    await _get_item(queue_item_id, session, auth)
    safe_name = FilePath(media_id).name
    if (
        safe_name != media_id
        or FilePath(safe_name).suffix.lower() not in VIDEO_EXTENSIONS
    ):
        raise HTTPException(status_code=400, detail="Некорректное имя видео")
    path = video_directory(queue_item_id) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Видео не найдено")
    return FileResponse(path)


@router.delete(
    "/{queue_item_id}/video/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить загруженное видео",
    responses=PERMISSION_CSRF_AUTH_RESPONSES,
)
async def delete_queue_video(
    queue_item_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[str, Path(min_length=1, max_length=120)],
    session: Session,
    auth: QueueEditDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> None:
    item = await _get_item(queue_item_id, session, auth)
    _ensure_not_reconciling(item)
    safe_name = FilePath(media_id).name
    if (
        safe_name != media_id
        or FilePath(safe_name).suffix.lower() not in VIDEO_EXTENSIONS
    ):
        raise HTTPException(status_code=400, detail="Некорректное имя видео")

    path = video_directory(queue_item_id) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Видео не найдено")
    path.unlink()
