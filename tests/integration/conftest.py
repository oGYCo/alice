"""Shared configuration and fixtures for integration tests.

Integration tests run against real services from docker-compose.yml:
  - PostgreSQL on localhost:5432 (database: alice_test)
  - Redis on localhost:6379
  - Neo4j on localhost:7687
  - Meilisearch on localhost:7700

The alice_test database is auto-created on the real PostgreSQL instance
if it does not already exist.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Default URLs pointing to the real docker-compose.yml services.
# The test database (alice_test) lives on the same PostgreSQL instance as
# production (alice), but is isolated by name.
# Override via environment variable if needed.
# ---------------------------------------------------------------------------

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://alice:alice@localhost:5432/alice_test"
)
DEFAULT_TEST_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_NEO4J_TEST_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_TEST_USER = "neo4j"
DEFAULT_NEO4J_TEST_PASS = "alice_neo4j"


def get_test_database_url() -> str:
    """Return the TEST_DATABASE_URL, falling back to the real-service default."""
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def get_test_redis_url() -> str:
    """Return the TEST_REDIS_URL, falling back to the real-service default."""
    return os.environ.get("TEST_REDIS_URL", DEFAULT_TEST_REDIS_URL)


def get_neo4j_test_uri() -> str:
    return os.environ.get("NEO4J_TEST_URI", DEFAULT_NEO4J_TEST_URI)


def get_neo4j_test_user() -> str:
    return os.environ.get("NEO4J_TEST_USER", DEFAULT_NEO4J_TEST_USER)


def get_neo4j_test_pass() -> str:
    return os.environ.get("NEO4J_TEST_PASS", DEFAULT_NEO4J_TEST_PASS)


def ensure_test_database() -> None:
    """Create the alice_test database on the real PostgreSQL if it doesn't exist.

    Uses synchronous psycopg2-style connection via asyncpg is not suitable here,
    so we use a plain SQLAlchemy synchronous engine with psycopg2 or pg8000.
    Falls back gracefully if the database already exists.
    """
    import asyncio

    import asyncpg

    async def _create_db() -> None:
        # Connect to the default 'alice' database to issue CREATE DATABASE
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="alice",
            password="alice",
            database="alice",
        )
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = 'alice_test'"
            )
            if not exists:
                await conn.execute("CREATE DATABASE alice_test OWNER alice")
        finally:
            await conn.close()

    try:
        asyncio.run(_create_db())
    except Exception:
        # Connection failed — PostgreSQL likely not running; tests will skip
        pass
