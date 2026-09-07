from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Ответ проверки работы HTTP-приложения."""

    status: Literal["ok"] = Field(description="Состояние приложения")


class DatabaseHealthResponse(HealthResponse):
    """Ответ проверки подключения к базе данных."""

    database: Literal["connected"] = Field(
        description="Состояние подключения к PostgreSQL"
    )
