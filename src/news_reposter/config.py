from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "News Reposter"
    vk_access_token: str | None = None
    vk_group: str | None = None
    vk_api_version: str = "5.199"
    vk_api_url: str = "https://api.vk.com/method"


@lru_cache
def get_settings() -> Settings:
    return Settings()

