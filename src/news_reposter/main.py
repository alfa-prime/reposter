from fastapi import FastAPI

from news_reposter.api.v1.vk import router as vk_router
from news_reposter.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Получение новостей VK для последующей публикации в MAX",
)

app.include_router(vk_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Показывает, что приложение запущено и отвечает на запросы."""

    return {"status": "ok"}
