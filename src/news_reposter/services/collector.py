import logging
from collections import defaultdict

from sqlalchemy import select

from news_reposter.config import get_settings
from news_reposter.db.models import Post, PostStatus, QueueItem, Source, Target, TargetSource
from news_reposter.db.session import async_session_factory
from news_reposter.integrations.vk import VKAPIError, VKClient

logger = logging.getLogger(__name__)


async def collect_active_sources_once() -> None:
    """Забирает последние посты активных VK-источников и создаёт очередь."""

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
                vk_post = await client.get_latest_post(source.url)
                if vk_post is None:
                    continue

                external_post_id = str(vk_post.id)
                post = await session.scalar(
                    select(Post).where(
                        Post.source_id == source_id,
                        Post.external_post_id == external_post_id,
                    )
                )
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

                for target_source in targets_by_source[source_id]:
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
                                post.original_text
                                if not target_source.rewrite_enabled
                                else None
                            ),
                        )
                    )

                post.status = PostStatus.PROCESSED
                await session.commit()
                logger.info(
                    "Источник %s обработан, пост %s",
                    source_id,
                    external_post_id,
                )
            except (VKAPIError, ValueError) as exc:
                await session.rollback()
                logger.exception("Ошибка сбора источника %s: %s", source_id, exc)
            except Exception:
                await session.rollback()
                logger.exception("Неожиданная ошибка сбора источника %s", source_id)
