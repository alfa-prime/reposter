from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated, Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    HttpClientDep,
    SameOriginDep,
    require_permission,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.config import get_settings
from news_reposter.db.models import MAXChannel
from news_reposter.db.session import get_db_session
from news_reposter.integrations.max import MAXAPIError, MAXClient

router = APIRouter(prefix="/max", tags=["MAX"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
MaxManageDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.TARGETS_MANAGE)),
]


def max_client_from_settings(http_client: httpx.AsyncClient) -> MAXClient:
    """Создаёт MAX-клиент из текущих настроек приложения."""

    settings = get_settings()
    if not settings.max_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_ACCESS_TOKEN не задан в .env",
        )
    return MAXClient(
        access_token=settings.max_access_token,
        http_client=http_client,
        api_url=settings.max_api_url,
    )


def max_bad_gateway(exc: MAXAPIError) -> HTTPException:
    """Преобразует ошибку MAX API в единый ответ нашего API."""

    suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Ошибка MAX{suffix}: {exc}",
    )


def normalize_max_link(value: str) -> str:
    """Приводит публичную ссылку MAX к единому виду для поиска в БД."""

    raw = value.strip()
    if not raw:
        raise ValueError("Ссылка на канал MAX не указана")

    if "://" not in raw:
        slug = raw.lstrip("@/")
        if not slug:
            raise ValueError("Ссылка на канал MAX не указана")
        return f"https://max.ru/{slug}"

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "max.ru",
        "www.max.ru",
    }:
        raise ValueError("Ожидается ссылка вида https://max.ru/channel_name")
    slug = parsed.path.strip("/")
    if not slug:
        raise ValueError("В ссылке не найдено имя канала")
    return f"https://max.ru/{slug}"


def event_datetime(timestamp_ms: object) -> datetime | None:
    """Преобразует timestamp MAX в datetime, если он корректен."""

    if not isinstance(timestamp_ms, int):
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


@router.post(
    "/webhook",
    summary="Webhook MAX",
    description=(
        "Публичный endpoint для событий MAX. Basic Auth на этом пути отключён, "
        "поэтому запрос обязательно проверяется по заголовку X-Max-Bot-Api-Secret."
    ),
    response_description="Подтверждение приёма события",
    responses={
        403: {"description": "Неверный секрет webhook"},
        503: {"description": "Webhook не настроен"},
    },
)
async def max_webhook(
    event: dict[str, Any],
    session: Session,
    http_client: HttpClientDep,
    x_max_bot_api_secret: Annotated[
        str | None,
        Header(alias="X-Max-Bot-Api-Secret"),
    ] = None,
) -> dict[str, Any]:
    """Принимает bot_added/bot_removed и сохраняет найденный MAX chat_id."""

    settings = get_settings()
    expected_secret = settings.max_webhook_secret
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_WEBHOOK_SECRET не задан",
        )
    if not x_max_bot_api_secret or not compare_digest(
        x_max_bot_api_secret,
        expected_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный секрет webhook",
        )

    update_type = event.get("update_type")
    if update_type not in {"bot_added", "bot_removed", "chat_title_changed"}:
        return {"ok": True, "ignored": True}

    chat_id = event.get("chat_id")
    if not isinstance(chat_id, int):
        return {"ok": True, "ignored": True}

    if update_type == "bot_added" and event.get("is_channel") is not True:
        return {"ok": True, "ignored": True}

    chat_info: dict[str, Any] = {}
    if update_type != "bot_removed":
        try:
            chat_info = await max_client_from_settings(http_client).get_chat(chat_id)
        except MAXAPIError as exc:
            raise max_bad_gateway(exc) from exc

    channel = await session.get(MAXChannel, chat_id)
    if channel is None:
        channel = MAXChannel(
            chat_id=chat_id,
            last_event_type=str(update_type),
        )
        session.add(channel)

    channel.is_active = update_type != "bot_removed"
    channel.last_event_type = str(update_type)
    channel.last_event_at = event_datetime(event.get("timestamp"))

    if chat_info:
        title = chat_info.get("title")
        if isinstance(title, str):
            channel.title = title[:200]
        link = chat_info.get("link")
        if isinstance(link, str) and link.strip():
            try:
                channel.link = normalize_max_link(link)
            except ValueError:
                channel.link = link.strip()[:2048]

    await session.commit()
    return {"ok": True, "chat_id": chat_id, "event": update_type}


@router.post(
    "/subscriptions/channel-discovery",
    summary="Подписать бота MAX на обнаружение каналов",
    description=(
        "Создаёт официальный Webhook через POST /subscriptions для событий "
        "bot_added, bot_removed и chat_title_changed. URL и secret берутся из .env."
    ),
    response_description="Результат создания подписки MAX",
    responses=PERMISSION_CSRF_AUTH_RESPONSES,
)
async def create_channel_discovery_subscription(
    _auth: MaxManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
    http_client: HttpClientDep,
) -> dict[str, Any]:
    """Создаёт webhook-подписку, через которую приложение получает chat_id."""

    settings = get_settings()
    if not settings.max_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_WEBHOOK_URL не задан",
        )
    if not settings.max_webhook_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX_WEBHOOK_URL должен начинаться с https://",
        )
    secret = settings.max_webhook_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX_WEBHOOK_SECRET не задан",
        )
    if (
        len(secret) < 5
        or len(secret) > 256
        or any(not (char.isalnum() or char in "_-") for char in secret)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX_WEBHOOK_SECRET должен содержать 5–256 символов A-Z, a-z, 0-9, _ или -",
        )

    try:
        return await max_client_from_settings(http_client).create_subscription(
            url=settings.max_webhook_url,
            secret=secret,
            update_types=["bot_added", "bot_removed", "chat_title_changed"],
        )
    except MAXAPIError as exc:
        raise max_bad_gateway(exc) from exc


@router.get(
    "/channel-id",
    summary="Получить MAX chat_id по публичной ссылке",
    description=(
        "Ищет канал среди уже обнаруженных webhook-событиями. Пользователь вводит "
        "публичную ссылку, а приложение возвращает сохранённый chat_id."
    ),
    response_description="Найденный MAX chat_id и данные канала",
    responses={
        **PERMISSION_AUTH_RESPONSES,
        404: {"description": "Канал ещё не обнаружен webhook-ом"},
    },
)
async def get_max_channel_id(
    _auth: MaxManageDep,
    session: Session,
    link: str = Query(
        description="Публичная ссылка MAX",
        examples=["https://max.ru/channel_51_news"],
    ),
) -> dict[str, Any]:
    """Возвращает chat_id ранее обнаруженного MAX-канала по ссылке."""

    try:
        normalized = normalize_max_link(link)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    channel = await session.scalar(
        select(MAXChannel).where(
            MAXChannel.link == normalized,
            MAXChannel.is_active.is_(True),
        )
    )
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Канал ещё не обнаружен. Если бот уже был в канале до включения "
                "подключения, MAX не пришлёт старое событие: один раз удалите бота "
                "из канала, затем снова добавьте его в подписчики и назначьте администратором."
            ),
        )

    return {
        "chat_id": channel.chat_id,
        "title": channel.title,
        "link": channel.link,
        "is_active": channel.is_active,
        "last_event_type": channel.last_event_type,
        "last_event_at": channel.last_event_at,
    }


@router.get(
    "/subscriptions",
    summary="Посмотреть Webhook-подписки MAX",
    description="Вызывает официальный GET /subscriptions и показывает активные подписки бота.",
    response_description="Текущие Webhook-подписки бота MAX",
    responses=PERMISSION_AUTH_RESPONSES,
)
async def get_max_subscriptions(
    _auth: MaxManageDep,
    http_client: HttpClientDep,
) -> dict[str, Any]:
    """Возвращает Webhook-подписки текущего MAX-бота."""

    try:
        return await max_client_from_settings(http_client).get_subscriptions()
    except MAXAPIError as exc:
        raise max_bad_gateway(exc) from exc
