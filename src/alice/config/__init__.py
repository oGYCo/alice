"""Application configuration using Pydantic Settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from .scoring import ScoringConfig


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://alice:alice@postgres:5432/alice"

    # Redis
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    REDIS_URL: str = "redis://redis:6379/0"

    # LLM - DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # LLM - Ollama (runs on host machine)
    OLLAMA_HOST: str = "http://host.docker.internal:11434"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_HOST: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"

    # Debug
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

__all__ = ["Settings", "ScoringConfig", "settings"]
