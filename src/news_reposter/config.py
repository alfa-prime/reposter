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

    http_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    http_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    http_max_connections: int = Field(default=50, ge=1, le=1000)
    http_max_keepalive_connections: int = Field(default=20, ge=0, le=1000)
    http_keepalive_expiry_seconds: float = Field(default=30.0, gt=0, le=600)
    http_trust_env: bool = False
    http_ca_file: str | None = None

    vk_access_token: str | None = None
    vk_group: str | None = None
    vk_api_version: str = "5.199"
    vk_api_url: str = "https://api.vk.com/method"

    max_access_token: str | None = None
    max_api_url: str = "https://platform-api2.max.ru"
    max_webhook_url: str | None = None
    max_webhook_secret: str | None = None

    llm_provider: str = "gigachat"
    llm_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    llm_default_rewrite_prompt: str = (
        "Ты редактор новостного канала. Перепиши исходную новость своими словами, "
        "сохрани все факты, имена, числа, даты и географические названия. Не добавляй "
        "факты от себя, не придумывай цитаты и не меняй смысл. Сделай текст естественным, "
        "понятным и готовым к публикации в социальной сети. Верни только готовый текст поста."
    )
    gigachat_credentials: str | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2-Pro"
    gigachat_api_url: str = "https://api.giga.chat/v1"
    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    postgres_db: str = "news_reposter"
    postgres_user: str = "news_reposter"
    postgres_password: str = "news_reposter"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_echo: bool = False

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
