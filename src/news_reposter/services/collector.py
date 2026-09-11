import logging
from collections import defaultdict

from sqlalchemy import select

from news_reposter.config import get_settings
from news_reposter.db.models import Post, PostStatus, QueueItem, Source, Target, TargetSource
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
    """Сохраняет один пост и создаёт недостающие QueueItem для его целей."""

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
