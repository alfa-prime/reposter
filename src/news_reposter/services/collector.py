import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from news_reposter.config import get_settings
from news_reposter.db.models import (
    AttachmentType,
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

logger = logging.getLogger(__name__)


async def collect_active_sources_once() -> None:
    """Забирает новые посты активных VK-источников и создаёт очередь."""

    settings = get_settings()
    if not settings.vk_access_token:
        logger.warning("Сбор пропущен: VK_ACCESS_TOKEN не настроен")
        return

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

        client = VKClient(
            access_token=settings.vk_access_token,
            api_version=settings.vk_api_version,
            api_url=settings.vk_api_url,
        )

        for source_id, source in sources.items():
            try:
                last_external_post_id = await _get_last_external_post_id(session, source_id)

                if last_external_post_id is None:
                    latest_post = await client.get_latest_post(source.url)
                    vk_posts = [latest_post] if latest_post is not None else []
                else:
                    vk_posts = await client.get_posts_after(
                        source.url,
                        last_external_post_id,
                    )

                if not vk_posts:
                    continue

                created_posts = 0
                for vk_post in vk_posts:
                    created = await _store_post_and_queue_items(
                        session=session,
                        source_id=source_id,
                        vk_post=vk_post,
                        target_sources=targets_by_source[source_id],
                    )
                    created_posts += int(created)

                await session.commit()
                logger.info(
                    "Источник %s обработан: новых постов %s",
                    source_id,
                    created_posts,
                )
            except (VKAPIError, ValueError) as exc:
                await session.rollback()
                logger.exception("Ошибка сбора источника %s: %s", source_id, exc)
            except Exception:
                await session.rollback()
                logger.exception("Неожиданная ошибка сбора источника %s", source_id)


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


async def _store_post_and_queue_items(
    *,
    session,
    source_id: int,
    vk_post: VKPost,
    target_sources: list[TargetSource],
) -> bool:
    """Сохраняет один пост, его вложения и создаёт QueueItem для целей."""

    external_post_id = str(vk_post.id)
    post = await session.scalar(
        select(Post).where(
            Post.source_id == source_id,
            Post.external_post_id == external_post_id,
        )
    )
    created = post is None

    if post is None:
        post = Post(
            source_id=source_id,
            external_post_id=external_post_id,
            source_url=vk_post.source_url,
            original_text=vk_post.text,
            source_published_at=vk_post.published_at,
            raw_data=vk_post.model_dump(mode="json"),
            status=PostStatus.RECEIVED,
        )
        session.add(post)
        await session.flush()

        for attachment in build_post_attachments(vk_post.attachments):
            attachment.post_id = post.post_id
            session.add(attachment)

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

    post.status = PostStatus.PROCESSED
    return created


def build_post_attachments(raw_attachments: list[dict[str, Any]]) -> list[PostAttachment]:
    """Преобразует вложения VK в универсальные PostAttachment."""

    result: list[PostAttachment] = []
    for position, raw_attachment in enumerate(raw_attachments):
        vk_type = str(raw_attachment.get("type", "other"))
        payload = raw_attachment.get(vk_type)
        payload_dict = payload if isinstance(payload, dict) else {}

        result.append(
            PostAttachment(
                attachment_type=_map_attachment_type(vk_type),
                external_attachment_id=_external_attachment_id(payload_dict),
                source_url=_attachment_source_url(vk_type, payload_dict),
                position=position,
                raw_data=raw_attachment,
            )
        )
    return result


def _map_attachment_type(vk_type: str) -> AttachmentType:
    mapping = {
        "photo": AttachmentType.PHOTO,
        "video": AttachmentType.VIDEO,
        "audio": AttachmentType.AUDIO,
        "doc": AttachmentType.DOCUMENT,
        "link": AttachmentType.LINK,
    }
    return mapping.get(vk_type, AttachmentType.OTHER)


def _external_attachment_id(payload: dict[str, Any]) -> str | None:
    attachment_id = payload.get("id")
    owner_id = payload.get("owner_id")
    if attachment_id is None:
        return None
    if owner_id is None:
        return str(attachment_id)
    return f"{owner_id}_{attachment_id}"


def _attachment_source_url(vk_type: str, payload: dict[str, Any]) -> str | None:
    if vk_type == "photo":
        return _best_photo_url(payload)

    if vk_type == "video":
        player = payload.get("player")
        if isinstance(player, str) and player:
            return player
        owner_id = payload.get("owner_id")
        video_id = payload.get("id")
        if owner_id is not None and video_id is not None:
            return f"https://vk.com/video{owner_id}_{video_id}"

    if vk_type in {"audio", "doc", "link"}:
        url = payload.get("url")
        if isinstance(url, str) and url:
            return url

    return None


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
