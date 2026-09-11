from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from news_reposter.api.v1.max import router as max_router
from news_reposter.api.v1.sources import router as sources_router
from news_reposter.api.v1.system import router as system_router
from news_reposter.api.v1.target_sources import router as target_sources_router
from news_reposter.api.v1.targets import router as targets_router
from news_reposter.api.v1.vk import router as vk_router
from news_reposter.config import get_settings
from news_reposter.db.session import close_database

settings = get_settings()

OPENAPI_TAGS = [
    {
        "name": "Система",
        "description": "Проверка работы приложения и подключения к PostgreSQL.",
    },
    {
        "name": "Источники",
        "description": "Управление площадками, из которых приложение получает посты.",
    },
    {
        "name": "Цели публикаций",
        "description": "Управление каналами и чатами для публикации готовых постов.",
    },
    {
        "name": "Источники целевого канала",
        "description": (
            "Подключение источников к конкретным целевым каналам и настройка "
            "их использования."
        ),
    },
    {
        "name": "VK",
        "description": "Получение исходных публикаций через API ВКонтакте.",
    },
    {
        "name": "MAX",
        "description": "Отправка текста и фотографий в канал MAX.",
    },
]


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
    description=(
        "Получает публикации из внешних источников, хранит очередь обработки "
        "и отправляет подготовленные посты в настроенные каналы."
    ),
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.include_router(vk_router, prefix="/api/v1")
app.include_router(max_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(targets_router, prefix="/api/v1")
app.include_router(target_sources_router, prefix="/api/v1")
app.include_router(system_router)
