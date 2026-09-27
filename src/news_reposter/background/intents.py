"""Domain snapshots: task payloads are immutable and contain no credentials."""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.v1.queue_media_state import load_state
from news_reposter.background.contracts import TaskQueue
from news_reposter.background.store import enqueue
from news_reposter.db.models import QueueItem
from news_reposter.services.publisher import (
    _publication_text,
    _source_photo_by_key,
    _uploaded_photo_path,
    _uploaded_video_paths,
)
from news_reposter.services.rewrite import RewriteService


def rewrite_snapshot(item: QueueItem) -> dict:
    context = RewriteService(None).context_for(item)
    return {
        "source_text": context.source_text,
        "system_prompt": context.system_prompt,
        "updated_at": item.updated_at.isoformat(),
        "rewritten_text": item.rewritten_text,
        "signature_text": item.signature_text,
        "status": item.status.value,
    }


def publication_snapshot(item: QueueItem) -> dict:
    media_order = load_state(item)
    files = []
    for key in media_order:
        path = _uploaded_photo_path(item.queue_item_id, key)
        if path is not None:
            stat = path.stat()
            files.append([path.name, stat.st_size, stat.st_mtime_ns])
    for path in _uploaded_video_paths(item.queue_item_id):
        stat = path.stat()
        files.append([path.name, stat.st_size, stat.st_mtime_ns])
    return {
        "text": _publication_text(item),
        "media_order": media_order,
        "source_photos": [
            [key, _source_photo_by_key(item, key)]
            for key in media_order
            if key.startswith("source:")
        ],
        "files": files,
        "target_external_id": item.target.external_id,
        "target_platform": item.target.platform,
        "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
    }


def snapshot_hash(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def enqueue_collection(
    session: AsyncSession,
    key: str,
    *,
    actor_user_id: int | None = None,
    trigger: str = "scheduled",
):
    return await enqueue(
        session,
        TaskQueue.COLLECTION,
        key,
        {"trigger": trigger},
        actor_user_id=actor_user_id,
        subject_id=0,
    )


async def enqueue_scheduled_publication(session: AsyncSession, item: QueueItem):
    snapshot = publication_snapshot(item)
    return await enqueue(
        session,
        TaskQueue.PUBLICATION,
        f"publication:scheduled:{item.queue_item_id}:{snapshot_hash(snapshot)}",
        {"snapshot": snapshot, "trigger": "scheduled"},
        subject_id=item.queue_item_id,
        target_id=item.target_id,
    )


async def enqueue_maintenance(session: AsyncSession):
    return await enqueue(
        session,
        TaskQueue.MAINTENANCE,
        "maintenance:media:" + datetime.now(UTC).date().isoformat(),
        {"operation": "media_cleanup"},
        subject_id=0,
    )
