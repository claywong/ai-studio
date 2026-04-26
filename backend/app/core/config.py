from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "G7E6 AI Studio"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    sub2api_base_url: str = "https://g7e6ai.com/api/v1"
    image_api_url: str = "https://g7e6ai.com/v1/images/generations"
    image_edit_api_url: str = "https://g7e6ai.com/v1/images/edits"
    image_edit_field_name: str = "image[]"
    image_api_key: str = ""
    request_timeout_seconds: float = 360.0
    dawclaudecode_webhook_secret: str = ""
    sub2api_admin_api_key: str = ""
    database_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
