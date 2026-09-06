from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from news_reposter.api.v1.max import router as max_router
from news_reposter.api.v1.system import router as system_router
from news_reposter.api.v1.vk import router as vk_router
from news_reposter.config import get_settings
from news_reposter.db.session import close_database

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Закрывает пул соединений с базой при остановке приложения."""

    try:
        yield
    finally:
        await close_database()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Получение новостей из VK и публикация в MAX",
    lifespan=lifespan,
)

app.include_router(vk_router, prefix="/api/v1")
app.include_router(max_router, prefix="/api/v1")
app.include_router(system_router)
