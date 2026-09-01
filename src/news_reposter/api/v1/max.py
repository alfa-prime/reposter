from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from news_reposter.config import get_settings
from news_reposter.integrations.max import MAXAPIError, MAXClient
from news_reposter.integrations.vk import VKAPIError, VKClient

router = APIRouter(prefix="/max", tags=["MAX"])


@router.post("/posts/from-vk/latest")
async def publish_latest_vk_post(
    group: str | None = Query(
        default=None,
        description="Ссылка, короткое имя или ID группы; по умолчанию VK_GROUP",
    ),
) -> dict[str, Any]:
    """Публикует в MAX последний обычный пост выбранной группы VK."""

    settings = get_settings()
    if not settings.vk_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK_ACCESS_TOKEN не задан в .env",
        )
    if not settings.max_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_ACCESS_TOKEN не задан в .env",
        )
    if settings.max_chat_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_CHAT_ID не задан в .env",
        )

    selected_group = group or settings.vk_group
    if not selected_group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Укажите параметр group или VK_GROUP в .env",
        )

    vk_client = VKClient(
        access_token=settings.vk_access_token,
        api_version=settings.vk_api_version,
        api_url=settings.vk_api_url,
    )
    max_client = MAXClient(
        access_token=settings.max_access_token,
        chat_id=settings.max_chat_id,
        api_url=settings.max_api_url,
        ca_file=settings.max_ca_file,
    )

    try:
        post = await vk_client.get_latest_post(selected_group)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="В группе не найдено ни одного поста",
            )

        photo_urls = post.photo_urls()
        result = await max_client.publish_post(
            text=post.text,
            image_urls=photo_urls,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except VKAPIError as exc:
        suffix = f" (код {exc.code})" if exc.code is not None else ""
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка VK{suffix}: {exc}",
        ) from exc
    except MAXAPIError as exc:
        suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка MAX{suffix}: {exc}",
        ) from exc

    return {
        "source_url": post.source_url,
        "photo_count": len(photo_urls),
        **result,
    }
