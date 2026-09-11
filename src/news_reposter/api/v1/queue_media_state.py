import json
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, status
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
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/data/media"))
STATE_FILENAME = ".media-state.json"


class QueueMediaState(BaseModel):
    """Выбранные фотографии публикации в нужном редактору порядке."""

    media_order: list[str] = Field(default_factory=list)


def item_dir(queue_item_id: int) -> Path:
    return MEDIA_ROOT / str(queue_item_id)


def state_path(queue_item_id: int) -> Path:
    return item_dir(queue_item_id) / STATE_FILENAME


def source_keys(item: Any) -> list[str]:
    post = getattr(item, "post", None)
    if post is None:
        return []
    result: list[tuple[int, str]] = []
    for attachment in getattr(post, "attachments", []):
        if attachment.attachment_type != AttachmentType.PHOTO or not attachment.source_url:
            continue
        result.append((attachment.position, f"source:{attachment.attachment_id}"))
    return [key for _, key in sorted(result)]


def uploaded_keys(queue_item_id: int) -> list[str]:
    directory = item_dir(queue_item_id)
    if not directory.exists():
        return []
    files = [
        path for path in directory.iterdir()
        if path.is_file() and path.name != STATE_FILENAME
    ]
    files.sort(key=lambda path: path.stat().st_mtime)
    return [f"upload:{path.name}" for path in files]


def available_keys(item: Any) -> list[str]:
    return source_keys(item) + uploaded_keys(item.queue_item_id)


def load_state(item: Any) -> list[str]:
    available = available_keys(item)
    path = state_path(item.queue_item_id)
    if not path.exists():
        return available
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return available
    if not isinstance(saved, list):
        return available
    return [key for key in saved if key in available]


def save_state(queue_item_id: int, media_order: list[str]) -> None:
    directory = item_dir(queue_item_id)
    directory.mkdir(parents=True, exist_ok=True)
    state_path(queue_item_id).write_text(
        json.dumps(media_order, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get(
    "/{queue_item_id}/media-state",
    response_model=QueueMediaState,
    summary="Получить выбранные фото публикации",
)
async def get_media_state(
    queue_item_id: Annotated[int, ApiPath(gt=0)],
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueMediaState:
    item = await QueueItemRepository(session).get(queue_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")
    return QueueMediaState(media_order=load_state(item))


@router.put(
    "/{queue_item_id}/media-state",
    response_model=QueueMediaState,
    summary="Изменить набор и порядок фото публикации",
    description=(
        "Сохраняет фотографии, которые войдут в публикацию, и их порядок. "
        "Фото, которых нет в media_order, считаются исключёнными из публикации."
    ),
)
async def update_media_state(
    queue_item_id: Annotated[int, ApiPath(gt=0)],
    data: QueueMediaState,
    session: Session,
    _api_key: ApiKeyDep,
) -> QueueMediaState:
    item = await QueueItemRepository(session).get(queue_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Элемент очереди не найден")

    available = set(available_keys(item))
    if len(data.media_order) != len(set(data.media_order)):
        raise HTTPException(status_code=400, detail="Фотография не может повторяться в порядке публикации")
    unknown = [key for key in data.media_order if key not in available]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестные фотографии: {', '.join(unknown)}",
        )

    save_state(queue_item_id, data.media_order)
    return QueueMediaState(media_order=data.media_order)
