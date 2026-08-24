from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PERSONAL_AFFAIRS_", env_file=".env")

    app_env: str = "development"
    database_url: str = "postgresql://personal_affairs:personal_affairs@127.0.0.1:15444/personal_affairs"
    database_min_size: int = 1
    database_max_size: int = 5
    session_cookie_name: str = "pa_session"
    csrf_header_name: str = "x-csrf-token"
    default_timezone: str = "Asia/Shanghai"
    bootstrap_username: str | None = None
    bootstrap_password: str | None = None
    feishu_webhook_url: str | None = Field(default=None, repr=False)
    ntfy_topic_url: str | None = Field(default=None, repr=False)
    vapid_public_key: str | None = None
    vapid_private_key: str | None = Field(default=None, repr=False)
    vapid_subject: str = "mailto:admin@example.com"
    notification_provider_timeout_seconds: float = 8.0
    reminder_poll_seconds: float = 5.0
    reminder_lease_seconds: int = 60
    reminder_batch_size: int = 20
    reminder_max_attempts: int = 6
    webhook_poll_seconds: float = 5.0
    webhook_batch_size: int = 20
    webhook_lease_seconds: int = 60
    webhook_max_attempts: int = 6
    webhook_timeout_seconds: float = 8.0
    feishu_im_enabled: bool = False
    feishu_im_verification_token: str | None = Field(default=None, repr=False)
    feishu_im_encrypt_key: str | None = Field(default=None, repr=False)
    feishu_im_default_user_id: UUID | None = None
    feishu_im_default_username: str | None = None
    tmeet_enabled: bool = False
    tmeet_bin: str = "tmeet"
    tmeet_timeout_seconds: float = 8.0
    tmeet_home: str | None = Field(default=None, repr=False)
    tmeet_allowed_commands: str = "meeting:get"


@lru_cache
def get_settings() -> Settings:
    return Settings()
