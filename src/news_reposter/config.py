from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения и файла .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Сервис публикации новостей"
    api_key: str | None = None
    vk_access_token: str | None = None
    vk_group: str | None = None
    vk_api_version: str = "5.199"
    vk_api_url: str = "https://api.vk.com/method"

    max_access_token: str | None = None
    max_chat_id: int | None = None
    max_api_url: str = "https://platform-api2.max.ru"
    max_ca_file: str | None = None

    postgres_db: str = "news_reposter"
    postgres_user: str = "news_reposter"
    postgres_password: str = "news_reposter"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_echo: bool = False

    collection_enabled: bool = True
    collection_interval_minutes: int = Field(default=15, ge=1, le=1440)
    collection_start_hour: int = Field(default=8, ge=0, le=23)
    collection_end_hour: int = Field(default=20, ge=0, le=23)
    collection_timezone: str = "Europe/Moscow"

    @property
    def database_url(self) -> str:
        """Собирает URL подключения к PostgreSQL для асинхронного драйвера."""

        url = URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    """Возвращает общий экземпляр настроек для всего приложения."""

    # Настройки не меняются во время работы, поэтому перечитывать .env не нужно.
    return Settings()
