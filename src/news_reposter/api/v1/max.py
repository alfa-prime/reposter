from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, status

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.config import get_settings
from news_reposter.integrations.max import MAXAPIError, MAXClient
from news_reposter.integrations.vk import VKAPIError, VKClient
from news_reposter.schemas import MAXPublishResponse

router = APIRouter(prefix="/max", tags=["MAX"], responses=API_KEY_RESPONSES)


def extract_max_chat_link(value: str) -> str:
    """Извлекает короткое имя публичного канала из ссылки MAX."""

    raw = value.strip()
    if not raw:
        raise ValueError("Ссылка на канал MAX не указана")

    if "://" not in raw:
        return raw.lstrip("@/")

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "max.ru",
        "www.max.ru",
    }:
        raise ValueError("Ожидается публичная ссылка вида https://max.ru/channel_name")

    chat_link = parsed.path.strip("/").split("/")[-1]
    if not chat_link:
        raise ValueError("В ссылке не найдено короткое имя канала")
    return chat_link.lstrip("@")


@router.get(
    "/channel/by-link",
    summary="Тест: получить MAX chat_id по публичной ссылке",
    description=(
        "Тестовый метод. Принимает публичную ссылку MAX, извлекает короткое имя "
        "канала и вызывает официальный GET /chats/{chatLink}. Возвращает ответ MAX, "
        "в том числе chat_id."
    ),
    response_description="Информация о публичном канале MAX",
    responses={
        422: {"description": "Некорректная ссылка"},
        502: {"description": "MAX API вернул ошибку"},
        503: {"description": "MAX_ACCESS_TOKEN не настроен"},
    },
)
async def get_max_channel_by_link(
    _api_key: ApiKeyDep,
    link: str = Query(
        description="Публичная ссылка или короткое имя канала MAX",
        examples=["https://max.ru/channel_news51", "channel_news51"],
    ),
) -> dict[str, Any]:
    """Проверяет возможность получить chat_id публичного канала по ссылке."""

    settings = get_settings()
    if not settings.max_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_ACCESS_TOKEN не задан в .env",
        )

    try:
        chat_link = extract_max_chat_link(link)
        client = MAXClient(
            access_token=settings.max_access_token,
            api_url=settings.max_api_url,
            ca_file=settings.max_ca_file,
        )
        result = await client.get_channel_by_link(chat_link)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except MAXAPIError as exc:
        suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка MAX{suffix}: {exc}",
        ) from exc

    return {
        "requested_link": link,
        "chat_link": chat_link,
        **result,
    }


@router.post(
    "/posts/from-vk/latest",
    response_model=MAXPublishResponse,
    summary="Опубликовать последний пост VK в MAX",
    description=(
        "Получает последний обычный пост выбранной группы VK и сразу отправляет "
        "его текст и фотографии в канал MAX, настроенный через `.env`."
    ),
    response_description="Результат публикации, ссылка на источник и число фотографий",
    responses={
        404: {"description": "В группе VK нет постов"},
        422: {"description": "Неверная группа или содержимое поста"},
        502: {"description": "Ошибка VK API или MAX API"},
        503: {"description": "Не настроены обязательные параметры интеграций"},
    },
)
async def publish_latest_vk_post(
    _api_key: ApiKeyDep,
    group: str | None = Query(
        default=None,
        description=(
            "Группа VK для разовой публикации. Если параметр не передан, "
            "используется `VK_GROUP` из `.env`."
        ),
        examples=["https://vk.ru/peninsula51", "peninsula51"],
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
