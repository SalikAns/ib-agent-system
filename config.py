"""
IB AI Agent System — Configuration Module

Uses pydantic-settings to load environment variables.
Works without a .env file (Railway provides vars at runtime).
"""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str
    allowed_user_ids: List[int] = []
    webhook_secret: str = "changeme-set-this-in-railway"
    gemini_api_key: str
    groq_api_key: Optional[str] = None
    ollama_url: Optional[str] = None
    port: int = 8080
    log_level: str = "INFO"
    db_path: str = "/app/data/agent.db"
    webhook_url: Optional[str] = None

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate Telegram bot token format."""
        if not re.match(r"^\d+:[A-Za-z0-9_-]{35,}$", v):
            raise ValueError(
                "Invalid token format: expected <id>:<hash>"
            )
        return v

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v) -> List[int]:
        """Parse comma-separated user ID string into list of ints."""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(uid.strip()) for uid in v.split(",") if uid.strip()]
        return v if v else []

    @field_validator("port", mode="before")
    @classmethod
    def parse_port(cls, v) -> int:
        """Parse port from string (Railway injects PORT as string)."""
        if isinstance(v, str):
            return int(v)
        return v


try:
    settings = Settings()
except Exception as exc:
    print(f"❌ Configuration error: {exc}")
    print("   → Check your environment variables or .env file.")
    print("   → Required: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY")
    print("   → See .env.template for all options.")
    raise SystemExit(1)
