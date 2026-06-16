from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend 的父目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

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

    # sub2api ops error webhook
    ops_webhook_secret: str = ""

    # Anthropic SDK for LLM-based error rule judgment
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"

    # Feishu Bot for DM notification
    lark_app_id: str = ""
    lark_app_secret: str = ""

    # Tencent Cloud COS — request_logs 归档
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = "ap-shanghai"
    cos_bucket: str = ""
    cos_endpoint: str = ""  # 留空则由 SDK 按 region/bucket 自动拼接

    # request_logs 归档行为
    archive_prefix: str = "request-logs"
    archive_retention_hours: int = 48
    archive_max_rows_per_part: int = 50000
    archive_delete_batch_size: int = 5000


@lru_cache
def get_settings() -> Settings:
    return Settings()
