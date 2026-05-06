"""Pydantic-settings based configuration for Paperclip Runtime Allocator.

All settings are loaded from environment variables with PAPERCLIP_ prefix.

Usage:
    from runtime_allocator.config import settings
    port = settings.port
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paperclip runtime allocator configuration."""

    # Service
    port: int = Field(default=8080, alias="PAPERCLIP_PORT")
    host: str = Field(default="0.0.0.0", alias="PAPERCLIP_HOST")
    log_level: str = Field(default="INFO", alias="PAPERCLIP_LOG_LEVEL")

    # Auth — production MUST set PAPERCLIP_API_KEYS; empty default = locked down
    api_keys: str = Field(default="", alias="PAPERCLIP_API_KEYS")

    # Rate limiting
    rate_limit_rps: float = Field(default=10.0, alias="PAPERCLIP_RATE_LIMIT_RPS")
    rate_limit_burst: int = Field(default=20, alias="PAPERCLIP_RATE_LIMIT_BURST")

    # Webhooks
    webhook_url: str = Field(default="", alias="PAPERCLIP_WEBHOOK_URL")
    webhook_secret: str = Field(default="", alias="PAPERCLIP_WEBHOOK_SECRET")

    # Database
    db_path: str = Field(
        default="~/.paperclip/runtime_state.sqlite",
        alias="PAPERCLIP_DB_PATH",
    )
    pg_uri: str = Field(default="", alias="PAPERCLIP_PG_URI")

    # Probes — default 0 disables background scheduler until fully tested
    probe_interval_seconds: int = Field(
        default=0, alias="PAPERCLIP_PROBE_INTERVAL_SECONDS"
    )

    # Billing
    default_daily_budget_usd: float = Field(
        default=10.0, alias="PAPERCLIP_DEFAULT_DAILY_BUDGET_USD"
    )

    model_config = {"env_prefix": "PAPERCLIP_", "case_sensitive": False}


settings = Settings()
