import asyncio
import logging
import mimetypes
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from news_reposter.api.v1.queue_media_state import load_state
from news_reposter.api.v1.queue_video import video_directory
from news_reposter.config import get_settings
from news_reposter.db.models import (
    AttachmentType,
    Post,
    Publication,
    PublicationStatus,
    QueueItem,
    QueueItemStatus,
)
from news_reposter.integrations.max import MAXAPIError, MAXClient
from news_reposter.services.media_storage import queue_item_directory

logger = logging.getLogger(__name__)


class PublicationError(RuntimeError):
    """Ошибка подготовки или отправки публикации."""


def _publication_text(item: QueueItem) -> str:
    text = (item.rewritten_text or item.post.original_text or "").strip()
    signature = (
        item.signature_text
        if item.signature_text is not None
        else item.target.default_signature
    )
    if signature and signature.strip():
        text = f"{text}\n\n{signature.strip()}" if text else signature.strip()

    # В редакторе подчёркивание пока хранится HTML-тегом, а MAX Markdown
    # использует ++текст++. Остальная наша разметка уже совместима с Markdown.
    text = re.sub(r"<u>(.*?)</u>", r"++\1++", text, flags=re.IGNORECASE | re.DOTALL)
    if len(text) > 4000:
        raise PublicationError(
            f"Текст вместе с подписью содержит {len(text)} символов; лимит MAX — 4000"
        )
    return text


def _source_photo_by_key(item: QueueItem, key: str) -> str | None:
    if not key.startswith("source:"):
        return None
    try:
        attachment_id = int(key.split(":", 1)[1])
    except ValueError:
        return None
    for attachment in item.post.attachments:
        if (
            attachment.attachment_id == attachment_id
            and attachment.attachment_type == AttachmentType.PHOTO
            and attachment.source_url
        ):
            return attachment.source_url
    return None


def _uploaded_photo_path(queue_item_id: int, key: str) -> Path | None:
    if not key.startswith("upload:"):
        return None
    filename = Path(key.split(":", 1)[1]).name
    if not filename:
        return None
    path = queue_item_directory(queue_item_id) / filename
    return path if path.is_file() else None


def _uploaded_video_paths(queue_item_id: int) -> list[Path]:
    directory = video_directory(queue_item_id)
    if not directory.exists():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_file()],
        key=lambda path: path.stat().st_mtime,
    )


def _mime_for_path(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime
    suffix = path.suffix.lower()
    fallback = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
    }
    if suffix not in fallback:
        raise PublicationError(f"Не удалось определить тип файла {path.name}")
    return fallback[suffix]


async def _max_attachments(item: QueueItem, client: MAXClient) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    # Фото публикуются строго в выбранном редактором порядке.
    for key in load_state(item):
        source_url = _source_photo_by_key(item, key)
        if source_url:
            result.append({"type": "image", "payload": {"url": source_url}})
            continue

        path = _uploaded_photo_path(item.queue_item_id, key)
        if path is None:
            continue
        token = await client.upload_media(
            media_type="image",
            filename=path.name,
            content=path.read_bytes(),
            content_type=_mime_for_path(path),
        )
        result.append({"type": "image", "payload": {"token": token}})

    # Исходное видео VK пока не импортируем. Все видео, загруженные редактором,
    # отправляем через официальный /uploads MAX и прикрепляем по token.
    for path in _uploaded_video_paths(item.queue_item_id):
        token = await client.upload_media(
            media_type="video",
            filename=path.name,
            content=path.read_bytes(),
            content_type=_mime_for_path(path),
        )
        result.append({"type": "video", "payload": {"token": token}})

    if len(result) > 12:
        raise PublicationError(
            f"В публикации выбрано {len(result)} медиафайлов; MAX разрешает максимум 12"
        )
    return result


async def _publish_with_media_retry(
    client: MAXClient,
    *,
    text: str,
    attachments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Повторяет отправку, пока MAX завершает обработку загруженного видео."""

    delays = (2, 4, 8, 12)
    for attempt in range(len(delays) + 1):
        try:
            return await client.publish_post(
                text=text,
                attachments=attachments,
                text_format="markdown",
            )
        except MAXAPIError as exc:
            detail = str(exc).lower()
            media_not_ready = (
                "attachment.not.ready" in detail
                or "file.not.processed" in detail
                or "attachment.file.not.processed" in detail
            )
            if not media_not_ready or attempt >= len(delays):
                raise
            await asyncio.sleep(delays[attempt])

    raise RuntimeError("unreachable")


def _message_fields(response: dict[str, Any]) -> tuple[str | None, str | None]:
    message = response.get("message")
    if not isinstance(message, dict):
        message = response
    body = message.get("body") if isinstance(message, dict) else None
    mid = body.get("mid") if isinstance(body, dict) else None
    url = message.get("url") if isinstance(message, dict) else None
    return (
        str(mid) if mid is not None else None,
        url if isinstance(url, str) and url else None,
    )


async def _loaded_item(
    session: AsyncSession,
    queue_item_id: int,
    *,
    for_update: bool = False,
) -> QueueItem | None:
    statement = (
        select(QueueItem)
        .options(
            selectinload(QueueItem.post).selectinload(Post.attachments),
            selectinload(QueueItem.target),
            selectinload(QueueItem.publication),
        )
        .where(QueueItem.queue_item_id == queue_item_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def publish_queue_item(
    session: AsyncSession,
    queue_item_id: int,
    http_client: httpx.AsyncClient,
    *,
    allow_scheduled: bool = True,
) -> QueueItem:
    """Публикует согласованный, запланированный или ранее упавший QueueItem в MAX."""

    # Блокировка строки сериализует ручной запуск и все экземпляры планировщика.
    # Проверка PublicationStatus выполняется до освобождающего блокировку commit.
    item = await _loaded_item(session, queue_item_id, for_update=True)
    if item is None:
        raise PublicationError("Элемент очереди не найден")
    allowed = {QueueItemStatus.APPROVED, QueueItemStatus.FAILED}
    if allow_scheduled:
        allowed.add(QueueItemStatus.SCHEDULED)
    if item.status not in allowed:
        raise PublicationError(f"Публикация недоступна для статуса {item.status.value}")

    publication = item.publication
    if publication is not None and publication.status == PublicationStatus.PUBLISHED:
        raise PublicationError("Этот пост уже опубликован")
    if publication is not None and publication.status == PublicationStatus.PUBLISHING:
        raise PublicationError("Публикация этого поста уже выполняется")

    if item.target.platform.lower() != "max":
        raise PublicationError("Автопубликация пока подключена только для MAX")
    if not item.target.is_active:
        raise PublicationError("Целевой канал отключён")

    settings = get_settings()
    if not settings.max_access_token:
        raise PublicationError("MAX_ACCESS_TOKEN не настроен")
    try:
        chat_id = int(item.target.external_id)
    except (TypeError, ValueError) as exc:
        raise PublicationError("У канала MAX некорректный chat_id") from exc

    if publication is None:
        publication = Publication(queue_item_id=item.queue_item_id)
        session.add(publication)
        await session.flush()

    publication.status = PublicationStatus.PUBLISHING
    publication.attempts += 1
    publication.error_message = None
    item.error_message = None
    await session.commit()

    started_at = time.perf_counter()

    try:
        client = MAXClient(
            access_token=settings.max_access_token,
            http_client=http_client,
            chat_id=chat_id,
            api_url=settings.max_api_url,
        )
        text = _publication_text(item)
        attachments = await _max_attachments(item, client)
        if not text and not attachments:
            raise PublicationError("Публикация не содержит текста или медиа")
        response = await _publish_with_media_retry(
            client,
            text=text,
            attachments=attachments,
        )
        mid, url = _message_fields(response)
    except Exception as exc:
        publication.status = PublicationStatus.FAILED
        publication.error_message = str(exc)
        item.status = QueueItemStatus.FAILED
        item.error_message = str(exc)
        await session.commit()
        logger.warning(
            "action=publish status=failed queue_item_id=%s target_id=%s platform=max attempt=%s duration_ms=%s error_type=%s",
            item.queue_item_id,
            item.target_id,
            publication.attempts,
            round((time.perf_counter() - started_at) * 1000),
            type(exc).__name__,
        )
        raise PublicationError(str(exc)) from exc

    publication.status = PublicationStatus.PUBLISHED
    publication.external_message_id = mid
    publication.publication_url = url
    publication.published_at = datetime.now(UTC)
    publication.error_message = None
    item.status = QueueItemStatus.PUBLISHED
    item.scheduled_at = None
    item.error_message = None
    await session.commit()

    logger.info(
        "action=publish status=success queue_item_id=%s target_id=%s platform=max attempt=%s media_count=%s duration_ms=%s",
        item.queue_item_id,
        item.target_id,
        publication.attempts,
        len(attachments),
        round((time.perf_counter() - started_at) * 1000),
    )

    refreshed = await _loaded_item(session, queue_item_id)
    assert refreshed is not None
    return refreshed


async def publish_due_items(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
) -> tuple[int, int]:
    """Публикует все MAX-посты, время которых уже наступило."""

    now = datetime.now(UTC)
    ids = list(
        (
            await session.scalars(
                select(QueueItem.queue_item_id)
                .where(
                    QueueItem.status == QueueItemStatus.SCHEDULED,
                    QueueItem.scheduled_at.is_not(None),
                    QueueItem.scheduled_at <= now,
                )
                .order_by(QueueItem.scheduled_at, QueueItem.queue_item_id)
            )
        ).all()
    )
    published = 0
    failed = 0
    for queue_item_id in ids:
        try:
            await publish_queue_item(session, queue_item_id, http_client)
            published += 1
        except PublicationError:
            failed += 1
    return published, failed
