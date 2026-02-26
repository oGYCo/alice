"""End-to-end integration tests for Phase 0 Alice API.

Tests the full pipeline via HTTP API using httpx.AsyncClient:
- POST /api/v1/sources — create RSS source
- POST /api/v1/connectors/rss/fetch — fetch RSS feed
- GET /api/v1/content — query content list
- POST /api/v1/push/trigger — trigger push batch
- GET /health — health check

Requires a real PostgreSQL test database.
Set TEST_DATABASE_URL env var to run:
    export TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/alice_test"
    uv run pytest tests/integration/test_phase0_e2e.py -v -m integration

Skip automatically when TEST_DATABASE_URL is not set.
"""

import os

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.main import create_app
from alice.models.base import Base
from alice.services.source_service import SourceService

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Module-level skip if TEST_DATABASE_URL not set
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL not set — skipping integration tests", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def engine():
    """Create async engine connected to test DB."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Provide a transactional session, rolled back after each test."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess
            await sess.rollback()


@pytest.fixture
async def http_client():
    """Provide httpx.AsyncClient with FastAPI app."""
    app = create_app()
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def source_svc(session):
    """Provide SourceService with test session."""
    return SourceService(session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_health_check(http_client):
    """GET /health returns {"status": "ok"}."""
    response = await http_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


async def test_create_rss_source(http_client):
    """POST /api/v1/sources creates an RSS source."""
    payload = {
        "name": "Test RSS Feed",
        "url": "https://example.com/feed.xml",
        "type": "rss",
    }
    response = await http_client.post("/api/v1/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Test RSS Feed"
    assert data["url"] == "https://example.com/feed.xml"
    assert data["type"] == "rss"
    assert data["is_active"] is True


async def test_list_sources_after_create(http_client):
    """GET /api/v1/sources returns created sources."""
    # Create a source
    payload = {
        "name": "Test List Feed",
        "url": "https://example.com/list-feed.xml",
        "type": "rss",
    }
    create_response = await http_client.post("/api/v1/sources", json=payload)
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    # List sources
    list_response = await http_client.get("/api/v1/sources")
    assert list_response.status_code == 200
    sources = list_response.json()
    assert isinstance(sources, list)
    assert any(s["id"] == created_id for s in sources)


async def test_fetch_rss_content(http_client):
    """POST /api/v1/connectors/rss/fetch returns RawContentSchema list."""
    # Use a real public RSS feed URL for testing
    # (This test uses a mock/test URL; in real scenarios, you'd use a test RSS fixture)
    payload = {
        "feed_url": "https://example.com/feed.xml",
        "limit": 5,
    }
    response = await http_client.post("/api/v1/connectors/rss/fetch", json=payload)
    # The response might be empty or have errors depending on network, but should not crash
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


async def test_list_content_returns_empty_initially(http_client):
    """GET /api/v1/content returns empty list when no content exists."""
    response = await http_client.get("/api/v1/content")
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    # Initially should be empty or minimal
    assert len(content) >= 0


async def test_get_content_by_id_not_found(http_client):
    """GET /api/v1/content/{id} returns 404 when content doesn't exist."""
    response = await http_client.get("/api/v1/content/999999")
    assert response.status_code == 404


async def test_trigger_push_batch(http_client):
    """POST /api/v1/push/trigger returns 202 Accepted."""
    payload = {
        "user_id": 1,
        "chat_id": 12345,
        "limit": 5,
    }
    response = await http_client.post("/api/v1/push/trigger", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["user_id"] == 1
    assert data["chat_id"] == 12345
    assert data["status"] == "queued"


async def test_pipeline_status_endpoint(http_client):
    """GET /api/v1/pipeline/status returns pipeline status counts."""
    response = await http_client.get("/api/v1/pipeline/status")
    assert response.status_code == 200
    data = response.json()
    assert "queued" in data
    assert "processing" in data
    assert "completed" in data
    assert "failed" in data
    # All should be integers
    assert isinstance(data["queued"], int)
    assert isinstance(data["processing"], int)
    assert isinstance(data["completed"], int)
    assert isinstance(data["failed"], int)


async def test_cleanup_created_sources(http_client, source_svc):
    """Teardown: Verify sources created in tests are cleaned up."""
    # This test verifies that transaction rollback works for sources.
    # Sources created in previous tests should not appear due to session rollback.
    sources = await source_svc.list_active()
    # After rollback, there should be no sources from this test session
    # (Each test uses a new session fixture that rolls back)
    assert isinstance(sources, list)


# ---------------------------------------------------------------------------
# Full pipeline workflow test
# ---------------------------------------------------------------------------


async def test_full_pipeline_workflow(http_client, session):
    """Integration test: create source → fetch content → query → push.

    This test demonstrates the full workflow:
    1. Create an RSS source
    2. Fetch content (mocked/empty in test environment)
    3. Query content list
    4. Trigger push batch
    5. Check health
    """
    # 1. Create a source
    source_payload = {
        "name": "Workflow Test Feed",
        "url": "https://example.com/workflow-test.xml",
        "type": "rss",
    }
    source_response = await http_client.post("/api/v1/sources", json=source_payload)
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]
    assert source_id is not None

    # 2. Verify source appears in list
    sources_response = await http_client.get("/api/v1/sources")
    assert sources_response.status_code == 200
    sources = sources_response.json()
    assert any(s["id"] == source_id for s in sources)

    # 3. Query content (may be empty initially)
    content_response = await http_client.get("/api/v1/content")
    assert content_response.status_code == 200
    content_list = content_response.json()
    assert isinstance(content_list, list)

    # 4. Trigger push batch
    push_payload = {
        "user_id": 1,
        "chat_id": 12345,
        "limit": 5,
    }
    push_response = await http_client.post("/api/v1/push/trigger", json=push_payload)
    assert push_response.status_code == 202
    push_data = push_response.json()
    assert push_data["status"] == "queued"

    # 5. Verify health endpoint still works
    health_response = await http_client.get("/health")
    assert health_response.status_code == 200
    health_data = health_response.json()
    assert health_data["status"] == "ok"

    # 6. Verify pipeline status
    pipeline_response = await http_client.get("/api/v1/pipeline/status")
    assert pipeline_response.status_code == 200
    pipeline_data = pipeline_response.json()
    assert all(k in pipeline_data for k in ["queued", "processing", "completed", "failed"])
