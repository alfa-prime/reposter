from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.db.session import get_db_session

router = APIRouter(tags=["System"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Показывает, что приложение запущено и отвечает на запросы."""

    return {"status": "ok"}


@router.get("/health/database")
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
