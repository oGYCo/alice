"""Unit tests for configuration module."""

from alice.config import Settings


def test_config_loads_with_defaults():
    """Test that Settings loads with default values."""
    settings = Settings()
    assert settings.DATABASE_URL.startswith("postgresql")
    assert settings.CELERY_BROKER_URL.startswith("redis")
    assert settings.REDIS_URL.startswith("redis")
    assert settings.OLLAMA_HOST == "http://host.docker.internal:11434"
    assert settings.DEBUG is False
    assert settings.LOG_LEVEL == "INFO"


def test_config_overrides_from_env(monkeypatch):
    """Test that Settings respects environment variable overrides."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/alice_test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DEBUG", "true")

    # Create fresh instance to pick up env vars
    settings = Settings()
    assert "test" in settings.DATABASE_URL
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.DEBUG is True


def test_config_debug_default_false():
    """Test that DEBUG defaults to False."""
    settings = Settings()
    assert settings.DEBUG is False
