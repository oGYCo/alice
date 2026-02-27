"""End-to-end integration tests for Phase 0 Alice API.

This suite runs against real dependencies:
- PostgreSQL test DB
- Redis broker for Celery dispatch
- Local HTTP RSS server (no connector override)

Required env vars:
    export TEST_DATABASE_URL="postgresql+asyncpg://alice:alice@localhost:5433/alice_test"
Optional env var:
    export TEST_REDIS_URL="redis://localhost:6380/0"
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import httpx
import pytest
import pytest_asyncio
import redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.config import settings
from alice.db import get_db
from alice.main import create_app
from alice.models.base import Base
from alice.services.source_service import SourceService
from alice.worker.celery_app import celery_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")

if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL not set — skipping integration tests", allow_module_level=True)


class _RSSFixtureHandler(BaseHTTPRequestHandler):
    feed_xml: bytes = b""
    article_bodies: dict[str, bytes] = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/feed.xml":
            self._write(200, self.feed_xml, "application/rss+xml; charset=utf-8")
            return

        article = self.article_bodies.get(parsed.path)
        if article is not None:
            self._write(200, article, "text/html; charset=utf-8")
            return

        self._write(404, b"not found", "text/plain; charset=utf-8")

    def _write(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        del format, args


def _build_feed_xml(base_url: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Alice Test Feed</title>
    <link>{base_url}</link>
    <description>Integration test feed</description>
    <item>
      <title>Integration Article One</title>
      <link>{base_url}/article-1.html?utm_source=integration</link>
      <guid>{base_url}/article-1</guid>
      <description>Article one description for integration test.</description>
      <pubDate>Fri, 27 Feb 2026 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Integration Article Two</title>
      <link>{base_url}/article-2.html?utm_medium=rss</link>
      <guid>{base_url}/article-2</guid>
      <description>Article two description for integration test.</description>
      <pubDate>Fri, 27 Feb 2026 01:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _build_article_html(title: str) -> bytes:
    return (
        "<html><body><article>"
        f"<h1>{title}</h1>"
        "<p>This is a realistic integration-test article body with enough content "
        "for extraction, dedup normalization, and downstream pipeline processing.</p>"
        "</article></body></html>"
    ).encode()


@pytest.fixture(scope="module", autouse=True)
def configure_real_broker() -> None:
    """Use a real Redis broker for Celery `.delay()` dispatches."""
    client = redis.Redis.from_url(TEST_REDIS_URL)
    try:
        client.ping()
    except redis.RedisError as exc:
        pytest.skip(f"Redis broker unavailable at {TEST_REDIS_URL}: {exc}")

    settings.CELERY_BROKER_URL = TEST_REDIS_URL
    settings.REDIS_URL = TEST_REDIS_URL
    celery_app.conf.broker_url = TEST_REDIS_URL
    celery_app.conf.result_backend = TEST_REDIS_URL

    client.flushdb()
    yield
    client.flushdb()
    client.close()


@pytest.fixture(scope="module")
def local_rss_server() -> dict[str, str]:
    """Start a local HTTP RSS server to avoid patching connector internals."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RSSFixtureHandler)
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    _RSSFixtureHandler.feed_xml = _build_feed_xml(base_url).encode("utf-8")
    _RSSFixtureHandler.article_bodies = {
        "/article-1.html": _build_article_html("Integration Article One"),
        "/article-2.html": _build_article_html("Integration Article Two"),
    }

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield {
            "base_url": base_url,
            "feed_url": f"{base_url}/feed.xml",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create async engine connected to test DB."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="module")
async def session(engine):
    """Provide a session with savepoint isolation."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with factory() as sess:
            yield sess
        await trans.rollback()


@pytest_asyncio.fixture(loop_scope="module")
async def http_client(engine):
    """Provide httpx.AsyncClient with FastAPI app wired to test DB and API key."""
    app = create_app()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": settings.ALICE_API_KEY},
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def source_svc(session):
    """Provide SourceService with test session."""
    return SourceService(session)


async def test_health_check(http_client):
    """GET /health returns {"status": "ok"}."""
    response = await http_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


async def test_create_rss_source(http_client, local_rss_server):
    """POST /api/v1/sources creates an RSS source with a real feed URL."""
    payload = {
        "name": "Test RSS Feed",
        "url": local_rss_server["feed_url"],
        "type": "rss",
    }
    response = await http_client.post("/api/v1/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Test RSS Feed"
    assert data["url"] == local_rss_server["feed_url"]
    assert data["type"] == "rss"
    assert data["is_active"] is True


async def test_list_sources_after_create(http_client, local_rss_server):
    """GET /api/v1/sources returns created sources."""
    payload = {
        "name": "Test List Feed",
        "url": local_rss_server["feed_url"],
        "type": "rss",
    }
    create_response = await http_client.post("/api/v1/sources", json=payload)
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    list_response = await http_client.get("/api/v1/sources")
    assert list_response.status_code == 200
    sources = list_response.json()
    assert isinstance(sources, list)
    assert any(s["id"] == created_id for s in sources)


async def test_fetch_rss_content(http_client, local_rss_server):
    """POST /api/v1/connectors/rss/fetch reads from local HTTP feed server."""
    payload = {
        "feed_url": local_rss_server["feed_url"],
        "limit": 5,
    }
    response = await http_client.post("/api/v1/connectors/rss/fetch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["source"] == "rss"


async def test_trigger_fetch_pipeline(http_client, local_rss_server):
    """POST /api/v1/pipeline/fetch/trigger runs real fetch for one known source."""
    source_payload = {
        "name": "Trigger Fetch Feed",
        "url": local_rss_server["feed_url"],
        "type": "rss",
    }
    source_response = await http_client.post("/api/v1/sources", json=source_payload)
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    response = await http_client.post(
        "/api/v1/pipeline/fetch/trigger",
        json={"source_id": source_id},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["sources_triggered"] == 1
    assert result["sources_fetched"] == 1
    assert result["items_fetched"] >= 1


async def test_list_content_returns_rows_after_fetch(http_client):
    """GET /api/v1/content should return fetched rows after real trigger."""
    response = await http_client.get("/api/v1/content")
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 1, content


async def test_get_content_by_id_not_found(http_client):
    """GET /api/v1/content/{id} returns 404 when content doesn't exist."""
    response = await http_client.get("/api/v1/content/999999")
    assert response.status_code == 404


async def test_trigger_push_batch(http_client):
    """POST /api/v1/pipeline/push/trigger dispatches through real Redis broker."""
    payload = {
        "user_id": 1,
        "chat_id": 12345,
        "limit": 5,
    }
    response = await http_client.post("/api/v1/pipeline/push/trigger", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["user_id"] == 1
    assert data["chat_id"] == 12345
    assert data["status"] == "queued"


async def test_pipeline_status_endpoint(http_client):
    """GET /api/v1/pipeline/status returns aggregate pipeline counts."""
    response = await http_client.get("/api/v1/pipeline/status")
    assert response.status_code == 200
    data = response.json()
    assert "queued" in data
    assert "processing" in data
    assert "completed" in data
    assert "failed" in data
    assert isinstance(data["queued"], int)
    assert isinstance(data["processing"], int)
    assert isinstance(data["completed"], int)
    assert isinstance(data["failed"], int)


async def test_cleanup_created_sources(source_svc):
    """Ensure source service query remains functional during teardown stage."""
    sources = await source_svc.list_active()
    assert isinstance(sources, list)


async def test_full_pipeline_workflow(http_client, local_rss_server):
    """Integration smoke: create source -> fetch trigger -> query -> push -> health."""
    source_payload = {
        "name": "Workflow Test Feed",
        "url": local_rss_server["feed_url"],
        "type": "rss",
    }
    source_response = await http_client.post("/api/v1/sources", json=source_payload)
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    sources_response = await http_client.get("/api/v1/sources")
    assert sources_response.status_code == 200
    sources = sources_response.json()
    assert any(s["id"] == source_id for s in sources)

    fetch_response = await http_client.post(
        "/api/v1/pipeline/fetch/trigger",
        json={"source_id": source_id},
    )
    assert fetch_response.status_code == 200
    fetch_result = fetch_response.json()
    assert fetch_result["sources_triggered"] == 1, fetch_result
    assert fetch_result["items_fetched"] >= 1, fetch_result

    content_response = await http_client.get("/api/v1/content")
    assert content_response.status_code == 200
    content_list = content_response.json()
    assert isinstance(content_list, list)
    assert len(content_list) >= 1

    push_payload = {
        "user_id": 1,
        "chat_id": 12345,
        "limit": 5,
    }
    push_response = await http_client.post("/api/v1/pipeline/push/trigger", json=push_payload)
    assert push_response.status_code == 202
    assert push_response.json()["status"] == "queued"

    health_response = await http_client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    pipeline_response = await http_client.get("/api/v1/pipeline/status")
    assert pipeline_response.status_code == 200
    pipeline_data = pipeline_response.json()
    assert all(k in pipeline_data for k in ["queued", "processing", "completed", "failed"])
