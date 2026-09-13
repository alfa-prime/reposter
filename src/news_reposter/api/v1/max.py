from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.config import get_settings
from news_reposter.integrations.max import MAXAPIError, MAXClient
from news_reposter.integrations.vk import VKAPIError, VKClient
from news_reposter.schemas import MAXPublishResponse

router = APIRouter(prefix="/max", tags=["MAX"], responses=API_KEY_RESPONSES)


def max_client_from_settings() -> MAXClient:
    """Создаёт MAX-клиент из текущих настроек приложения."""

    settings = get_settings()
    if not settings.max_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_ACCESS_TOKEN не задан в .env",
        )
    return MAXClient(
        access_token=settings.max_access_token,
        api_url=settings.max_api_url,
        ca_file=settings.max_ca_file,
    )


def max_bad_gateway(exc: MAXAPIError) -> HTTPException:
    """Преобразует ошибку MAX API в единый ответ нашего API."""

    suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Ошибка MAX{suffix}: {exc}",
    )


@router.get(
    "/updates",
    summary="Тест: получить последние события MAX",
    description=(
        "Тестовый Long Polling через официальный GET /updates. Нужен для поиска "
        "chat_id после добавления бота администратором канала. Если marker не "
        "передан, MAX возвращает последнее доступное обновление. Метод не работает, "
        "если у бота уже активен Webhook."
    ),
    response_description="Список событий MAX и marker для следующего запроса",
    responses={
        502: {"description": "MAX API вернул ошибку"},
        503: {"description": "MAX_ACCESS_TOKEN не настроен"},
    },
)
async def get_max_updates(
    _api_key: ApiKeyDep,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Максимальное количество событий",
    ),
    timeout: int = Query(
        default=0,
        ge=0,
        le=90,
        description="Ожидание Long Polling в секундах; для теста по умолчанию 0",
    ),
    marker: int | None = Query(
        default=None,
        description="Marker из предыдущего ответа; без него вернётся последнее событие",
    ),
    types: list[str] | None = Query(
        default=None,
        description=(
            "Необязательный фильтр типов событий. Например: bot_added,bot_started. "
            "Параметр можно передать несколько раз."
        ),
    ),
) -> dict[str, Any]:
    """Возвращает последние события MAX, в которых можно увидеть chat_id."""

    try:
        return await max_client_from_settings().get_updates(
            limit=limit,
            timeout=timeout,
            marker=marker,
            types=types,
        )
    except MAXAPIError as exc:
        raise max_bad_gateway(exc) from exc


@router.get(
    "/subscriptions",
    summary="Тест: посмотреть Webhook-подписки MAX",
    description=(
        "Вызывает официальный GET /subscriptions и показывает активные Webhook-"
        "подписки бота. Полезно для диагностики: при активном Webhook тестовый "
        "GET /updates через Long Polling использовать нельзя."
    ),
    response_description="Текущие Webhook-подписки бота MAX",
    responses={
        502: {"description": "MAX API вернул ошибку"},
        503: {"description": "MAX_ACCESS_TOKEN не настроен"},
    },
)
async def get_max_subscriptions(
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """Возвращает Webhook-подписки текущего MAX-бота."""

    try:
        return await max_client_from_settings().get_subscriptions()
    except MAXAPIError as exc:
        raise max_bad_gateway(exc) from exc


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
        raise max_bad_gateway(exc) from exc

    return {
        "source_url": post.source_url,
        "photo_count": len(photo_urls),
        **result,
    }
