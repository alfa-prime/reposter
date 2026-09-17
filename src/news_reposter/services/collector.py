import asyncio
import logging
from collections import defaultdict
from typing import Any

import httpx
from sqlalchemy import select

from news_reposter.config import get_settings
from news_reposter.db.models import (
    AttachmentType,
    CollectionRunStatus,
    CollectionRunTrigger,
    CollectionSourceRunStatus,
    Post,
    PostAttachment,
    PostStatus,
    QueueItem,
    Source,
    Target,
    TargetSource,
)
from news_reposter.db.session import async_session_factory
from news_reposter.integrations.vk import VKAPIError, VKClient, VKPost
from news_reposter.services.collection_history import CollectionHistory

logger = logging.getLogger(__name__)

_collection_lock: asyncio.Lock | None = None
_collection_lock_loop: asyncio.AbstractEventLoop | None = None


class CollectionAlreadyRunningError(RuntimeError):
    """Другой ручной или плановый проход уже обрабатывает источники."""


def _get_collection_lock() -> asyncio.Lock:
    """Возвращает блокировку для текущего event loop.

    Ручной запуск и планировщик используют один сборщик. Блокировка не даёт им
    одновременно читать одну и ту же точку продолжения и создавать дубликаты.
    Привязка к текущему loop также сохраняет предсказуемость изолированных тестов.
    """

    global _collection_lock, _collection_lock_loop

    loop = asyncio.get_running_loop()
    if _collection_lock is None or _collection_lock_loop is not loop:
        _collection_lock = asyncio.Lock()
        _collection_lock_loop = loop
    return _collection_lock


async def collect_active_sources_once(
    http_client: httpx.AsyncClient,
    trigger: CollectionRunTrigger = CollectionRunTrigger.MANUAL,
) -> dict[str, int]:
    """Забирает новые посты активных VK-источников и создаёт очередь."""

    lock = _get_collection_lock()
    if lock.locked():
        raise CollectionAlreadyRunningError("Сбор источников уже выполняется")
    async with lock:
        return await _collect_active_sources_once(
            http_client=http_client,
            trigger=trigger,
        )


async def _collect_active_sources_once(
    http_client: httpx.AsyncClient,
    trigger: CollectionRunTrigger = CollectionRunTrigger.MANUAL,
) -> dict[str, int]:
    """Выполняет один сериализованный проход сборщика."""

    history = CollectionHistory()
    run_id = await history.start_run(trigger)
    summary = {
        "run_id": run_id,
        "sources_total": 0,
        "sources_checked": 0,
        "sources_succeeded": 0,
        "posts_found": 0,
        "posts_created": 0,
        "queue_items_created": 0,
        "errors": 0,
    }

    settings = get_settings()
    if not settings.vk_access_token:
        logger.warning("Сбор пропущен: VK_ACCESS_TOKEN не настроен")
        error = RuntimeError("VK_ACCESS_TOKEN не настроен")
        await history.finish_run(
            run_id,
            status=CollectionRunStatus.FAILED,
            summary=summary,
            error=error,
        )
        return summary

    try:
        async with async_session_factory() as session:
            statement = (
                select(TargetSource, Source)
                .join(Source, Source.source_id == TargetSource.source_id)
                .join(Target, Target.target_id == TargetSource.target_id)
                .where(
                    TargetSource.is_active.is_(True),
                    Source.is_active.is_(True),
                    Target.is_active.is_(True),
                    Source.platform == "vk",
                )
                .order_by(Source.source_id, TargetSource.target_id)
            )
            rows = (await session.execute(statement)).all()

            targets_by_source: dict[int, list[TargetSource]] = defaultdict(list)
            sources: dict[int, Source] = {}
            for target_source, source in rows:
                targets_by_source[source.source_id].append(target_source)
                sources[source.source_id] = source
            summary["sources_total"] = len(sources)
            await history.set_sources_total(run_id, len(sources))

            client = VKClient(
                access_token=settings.vk_access_token,
                http_client=http_client,
                api_version=settings.vk_api_version,
                api_url=settings.vk_api_url,
            )

            for source_id, source in sources.items():
                summary["sources_checked"] += 1
                last_external_post_id: int | None = None
                posts_found = 0
                source_run_id = await history.start_source(
                    run_id=run_id,
                    source_id=source_id,
                    source_name=source.name,
                    source_url=source.url,
                    last_post_id_before=None,
                )
                try:
                    last_external_post_id = await _get_last_external_post_id(
                        session, source_id
                    )
                    await history.set_source_last_before(
                        source_run_id, last_external_post_id
                    )

                    if last_external_post_id is None:
                        latest_post = await client.get_latest_post(source.url)
                        vk_posts = [latest_post] if latest_post is not None else []
                    else:
                        vk_posts = await client.get_posts_after(
                            source.url,
                            last_external_post_id,
                        )
                    posts_found = len(vk_posts)
                    summary["posts_found"] += posts_found

                    if not vk_posts:
                        summary["sources_succeeded"] += 1
                        await history.finish_source(
                            source_run_id,
                            status=CollectionSourceRunStatus.NO_CHANGES,
                            last_post_id_after=last_external_post_id,
                            posts_found=0,
                            posts_created=0,
                            queue_items_created=0,
                        )
                        continue

                    created_posts = 0
                    created_queue_items = 0
                    for vk_post in vk_posts:
                        (
                            post_created,
                            queue_items_created,
                        ) = await _store_post_and_queue_items(
                            session=session,
                            source_id=source_id,
                            vk_post=vk_post,
                            target_sources=targets_by_source[source_id],
                        )
                        created_posts += int(post_created)
                        created_queue_items += queue_items_created

                    await session.commit()
                    summary["sources_succeeded"] += 1
                    summary["posts_created"] += created_posts
                    summary["queue_items_created"] += created_queue_items
                    await history.finish_source(
                        source_run_id,
                        status=CollectionSourceRunStatus.SUCCESS,
                        last_post_id_after=vk_posts[-1].id,
                        posts_found=posts_found,
                        posts_created=created_posts,
                        queue_items_created=created_queue_items,
                    )
                    logger.info(
                        "Источник %s обработан: новых постов %s, элементов очереди %s",
                        source_id,
                        created_posts,
                        created_queue_items,
                    )
                except (VKAPIError, ValueError) as exc:
                    summary["errors"] += 1
                    await session.rollback()
                    await history.finish_source(
                        source_run_id,
                        status=CollectionSourceRunStatus.FAILED,
                        last_post_id_after=last_external_post_id,
                        posts_found=posts_found,
                        posts_created=0,
                        queue_items_created=0,
                        error=exc,
                    )
                    logger.exception("Ошибка сбора источника %s", source_id)
                except Exception as exc:
                    summary["errors"] += 1
                    await session.rollback()
                    await history.finish_source(
                        source_run_id,
                        status=CollectionSourceRunStatus.FAILED,
                        last_post_id_after=last_external_post_id,
                        posts_found=posts_found,
                        posts_created=0,
                        queue_items_created=0,
                        error=exc,
                    )
                    logger.exception("Неожиданная ошибка сбора источника %s", source_id)
    except Exception as exc:
        await history.finish_run(
            run_id,
            status=CollectionRunStatus.FAILED,
            summary=summary,
            error=exc,
        )
        raise

    if summary["sources_total"] == 0:
        run_status = CollectionRunStatus.SKIPPED
    elif summary["errors"] == 0:
        run_status = CollectionRunStatus.SUCCESS
    elif summary["sources_succeeded"]:
        run_status = CollectionRunStatus.PARTIAL
    else:
        run_status = CollectionRunStatus.FAILED
    await history.finish_run(run_id, status=run_status, summary=summary)
    return summary


async def _get_last_external_post_id(session, source_id: int) -> int | None:
    """Возвращает ID самого свежего сохранённого поста VK для источника."""

    external_post_id = await session.scalar(
        select(Post.external_post_id)
        .where(Post.source_id == source_id)
        .order_by(Post.source_published_at.desc(), Post.post_id.desc())
        .limit(1)
    )
    if external_post_id is None:
        return None
    try:
        return int(external_post_id)
    except ValueError as exc:
        raise ValueError(
            f"Некорректный external_post_id у VK-источника {source_id}: "
            f"{external_post_id}"
        ) from exc


def _effective_vk_content(vk_post: VKPost) -> tuple[str, list[dict[str, Any]]]:
    """Возвращает текст и вложения, пригодные для редакционной очереди.

    У репостов VK верхний уровень записи может быть пустым, а исходный текст и
    вложения лежат в copy_history. В таком случае берём содержимое первого
    вложенного поста. Если верхний уровень содержит собственный текст или
    вложения, сохраняем именно его.
    """

    text = vk_post.text.strip()
    attachments = list(vk_post.attachments)
    if text or attachments:
        return text, attachments

    raw = vk_post.model_dump(mode="python")
    copy_history = raw.get("copy_history")
    if not isinstance(copy_history, list) or not copy_history:
        return "", []

    copied = copy_history[0]
    if not isinstance(copied, dict):
        return "", []

    copied_text = copied.get("text")
    text = copied_text.strip() if isinstance(copied_text, str) else ""
    copied_attachments = copied.get("attachments")
    attachments = (
        [item for item in copied_attachments if isinstance(item, dict)]
        if isinstance(copied_attachments, list)
        else []
    )
    return text, attachments


async def _store_post_and_queue_items(
    *,
    session,
    source_id: int,
    vk_post: VKPost,
    target_sources: list[TargetSource],
) -> tuple[bool, int]:
    """Сохраняет пост, фото/видео и создаёт QueueItem для целей."""

    external_post_id = str(vk_post.id)
    post = await session.scalar(
        select(Post).where(
            Post.source_id == source_id,
            Post.external_post_id == external_post_id,
        )
    )
    created = post is None

    effective_text, effective_attachments = _effective_vk_content(vk_post)
    post_attachments = build_post_attachments(effective_attachments)

    if post is None:
        post = Post(
            source_id=source_id,
            external_post_id=external_post_id,
            source_url=vk_post.source_url,
            original_text=effective_text,
            source_published_at=vk_post.published_at,
            raw_data=vk_post.model_dump(mode="json"),
            status=PostStatus.RECEIVED,
        )
        session.add(post)
        await session.flush()

        for attachment in post_attachments:
            attachment.post_id = post.post_id
            session.add(attachment)

    # Пустую запись без текста, фото и видео сохраняем только как маркер,
    # чтобы следующий сбор не забирал её снова. Видеопосты, напротив, должны
    # попасть в очередь даже если импорт самого видео из VK пока не реализован.
    if not post.original_text.strip() and not post_attachments:
        post.status = PostStatus.PROCESSED
        logger.info(
            "Пост VK %s источника %s пропущен: нет текста, фото или видео",
            external_post_id,
            source_id,
        )
        return created, 0

    queue_items_created = 0
    for target_source in target_sources:
        existing_queue_item = await session.scalar(
            select(QueueItem.queue_item_id).where(
                QueueItem.post_id == post.post_id,
                QueueItem.target_id == target_source.target_id,
            )
        )
        if existing_queue_item is not None:
            continue

        session.add(
            QueueItem(
                post_id=post.post_id,
                target_id=target_source.target_id,
                rewritten_text=(
                    post.original_text if not target_source.rewrite_enabled else None
                ),
            )
        )
        queue_items_created += 1

    post.status = PostStatus.PROCESSED
    return created, queue_items_created


def build_post_attachments(
    raw_attachments: list[dict[str, Any]],
) -> list[PostAttachment]:
    """Преобразует фотографии и видео VK во вложения в исходном порядке."""

    result: list[PostAttachment] = []
    for raw_attachment in raw_attachments:
        attachment_type = raw_attachment.get("type")
        if attachment_type == "photo":
            payload = raw_attachment.get("photo")
            photo = payload if isinstance(payload, dict) else {}
            result.append(
                PostAttachment(
                    attachment_type=AttachmentType.PHOTO,
                    external_attachment_id=_external_attachment_id(photo),
                    source_url=_best_photo_url(photo),
                    position=len(result),
                    raw_data=raw_attachment,
                )
            )
            continue

        if attachment_type == "video":
            payload = raw_attachment.get("video")
            video = payload if isinstance(payload, dict) else {}
            player = video.get("player")
            result.append(
                PostAttachment(
                    attachment_type=AttachmentType.VIDEO,
                    external_attachment_id=_external_attachment_id(video),
                    source_url=player if isinstance(player, str) and player else None,
                    position=len(result),
                    raw_data=raw_attachment,
                )
            )

    return result


def _external_attachment_id(payload: dict[str, Any]) -> str | None:
    attachment_id = payload.get("id")
    owner_id = payload.get("owner_id")
    if attachment_id is None:
        return None
    if owner_id is None:
        return str(attachment_id)
    return f"{owner_id}_{attachment_id}"


def _best_photo_url(photo: dict[str, Any]) -> str | None:
    original = photo.get("orig_photo")
    if isinstance(original, dict):
        url = original.get("url")
        if isinstance(url, str) and url:
            return url

    sizes = photo.get("sizes")
    if not isinstance(sizes, list):
        return None

    available_sizes = [
        size
        for size in sizes
        if isinstance(size, dict) and isinstance(size.get("url"), str)
    ]
    if not available_sizes:
        return None

    best_size = max(
        available_sizes,
        key=lambda size: int(size.get("width", 0)) * int(size.get("height", 0)),
    )
    return best_size["url"]
