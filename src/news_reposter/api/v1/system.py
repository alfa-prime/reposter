from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.api.dependencies import API_KEY_RESPONSES, ApiKeyDep
from news_reposter.config import get_settings
from news_reposter.db.session import get_db_session
from news_reposter.schemas import DatabaseHealthResponse, HealthResponse
from news_reposter.services.collector import collect_active_sources_once

router = APIRouter(tags=["Система"])


@router.get(
    "/health",
    summary="Проверить работу приложения",
    description="Возвращает успешный ответ, если HTTP-сервис запущен.",
    response_model=HealthResponse,
    response_description="Текущее состояние приложения",
)
async def health() -> dict[str, str]:
    """Показывает, что приложение запущено и отвечает на запросы."""

    return {"status": "ok"}


@router.get(
    "/health/database",
    summary="Проверить подключение к PostgreSQL",
    description=(
        "Выполняет простой запрос `SELECT 1` через асинхронную сессию "
        "SQLAlchemy."
    ),
    response_model=DatabaseHealthResponse,
    response_description="Состояние подключения к базе данных",
    responses={
        503: {"description": "PostgreSQL недоступен или вернул неверный ответ"},
    },
)
async def database_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Проверяет асинхронное подключение приложения к PostgreSQL."""

    try:
        result = await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL недоступен",
        ) from exc

    if result.scalar_one() != 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL вернул неожиданный ответ",
        )

    return {"status": "ok", "database": "connected"}


@router.post(
    "/api/v1/system/collect-now",
    summary="Запустить сбор источников сейчас",
    description=(
        "Немедленно запускает тот же сбор активных VK-источников, который обычно "
        "выполняется планировщиком. Удобно для ручной проверки и будущей админки."
    ),
    response_description="Сводка выполненного сбора",
    responses={
        **API_KEY_RESPONSES,
        503: {"description": "VK_ACCESS_TOKEN не настроен"},
    },
)
async def collect_now(_api_key: ApiKeyDep) -> dict[str, int | str]:
    """Запускает один проход сборщика вне расписания."""

    if not get_settings().vk_access_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK_ACCESS_TOKEN не задан в .env",
        )

    summary = await collect_active_sources_once()
    return {"status": "ok", **summary}
