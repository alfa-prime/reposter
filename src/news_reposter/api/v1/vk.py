from fastapi import APIRouter, HTTPException, Query, status

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.config import get_settings
from news_reposter.integrations.vk import VKAPIError, VKClient, VKPost

router = APIRouter(prefix="/vk", tags=["VK"], responses=API_KEY_RESPONSES)


@router.get(
    "/posts/latest",
    response_model=VKPost,
    summary="Получить последний пост VK",
    description=(
        "Возвращает последний обычный пост выбранной группы. Если первой записью "
        "идёт закреплённый пост, получает следующую запись стены."
    ),
    response_description="Последний обычный пост группы VK",
    responses={
        404: {"description": "В группе нет постов"},
        422: {"description": "Группа не указана или имеет неверный формат"},
        502: {"description": "VK API вернул ошибку"},
        503: {"description": "Не настроен токен VK"},
    },
)
async def get_latest_vk_post(
    _api_key: ApiKeyDep,
    group: str | None = Query(
        default=None,
        description=(
            "Ссылка `vk.ru` или `vk.com`, короткое имя, `club123` или числовой "
            "ID группы. Если параметр не передан, используется `VK_GROUP` из `.env`."
        ),
        examples=["https://vk.ru/peninsula51", "peninsula51", "club185052131"],
    ),
) -> VKPost:
    """Возвращает последний пост указанной или настроенной группы VK."""

    settings = get_settings()

    if not settings.vk_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK_ACCESS_TOKEN не задан в .env",
        )

    # Параметр запроса позволяет проверить другую группу без правки .env.
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
