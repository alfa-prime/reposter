"""Limit journal queries without changing timeouts for background writes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from news_reposter.config import get_settings
from news_reposter.db.session import get_db_session


async def get_journal_session(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[AsyncSession]:
    try:
        timeout = (
            f"{max(1, int(get_settings().database_journal_timeout_seconds * 1000))}ms"
        )
        await session.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": timeout},
        )
        yield session
    except (TimeoutError, PoolTimeoutError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Журнал временно недоступен. Повторите запрос."
        ) from exc
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) != "57014":
            raise
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Журнал временно недоступен. Повторите запрос."
        ) from exc


JournalSession = Annotated[AsyncSession, Depends(get_journal_session)]
