"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def test_env_override(monkeypatch):
    """Fixture to override environment variables for tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/alice_test")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6380/0")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6380/0")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    return monkeypatch
