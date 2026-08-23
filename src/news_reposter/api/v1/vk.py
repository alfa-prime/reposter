from fastapi import APIRouter, HTTPException, Query, status

from news_reposter.config import get_settings
from news_reposter.integrations.vk import VKAPIError, VKClient, VKPost

router = APIRouter(prefix="/vk", tags=["VK"])


@router.get("/posts/latest", response_model=VKPost)
async def get_latest_vk_post(
    group: str | None = Query(
        default=None,
        description="Ссылка, короткое имя или ID группы; по умолчанию VK_GROUP",
    ),
) -> VKPost:
    settings = get_settings()

    if not settings.vk_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK_ACCESS_TOKEN не задан в .env",
        )

    selected_group = group or settings.vk_group
    if not selected_group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Укажите параметр group или VK_GROUP в .env",
        )

    client = VKClient(
        access_token=settings.vk_access_token,
        api_version=settings.vk_api_version,
        api_url=settings.vk_api_url,
    )

    try:
        post = await client.get_latest_post(selected_group)
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

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="В группе не найдено ни одного поста",
        )

    return post

