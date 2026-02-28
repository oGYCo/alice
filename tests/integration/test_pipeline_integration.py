"""Integration tests for PipelineOrchestrator with real Redis dispatch path.

Runs against real services from docker-compose.yml:
- PostgreSQL (localhost:5432, database: alice_test)
- Redis broker for Celery .delay() (localhost:6379)

Override with TEST_DATABASE_URL / TEST_REDIS_URL env vars if needed.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
import redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.config import settings
from alice.models import Base
from alice.models.content import Content, PipelineStatus
from alice.pipeline.orchestrator import PipelineOrchestrator
from alice.schemas.content import RawContentSchema
from alice.services.storage import ContentStorageService
from alice.worker.celery_app import celery_app

from .conftest import ensure_test_database, get_test_database_url, get_test_redis_url

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

ensure_test_database()
TEST_DATABASE_URL = get_test_database_url()
TEST_REDIS_URL = get_test_redis_url()


@pytest.fixture(scope="module", autouse=True)
def configure_real_broker() -> None:
    """Configure Celery to use a real Redis broker for dispatch assertions."""
    client = redis.Redis.from_url(TEST_REDIS_URL)
    try:
        client.ping()
    except redis.RedisError as exc:
        pytest.skip(f"Redis broker unavailable at {TEST_REDIS_URL}: {exc}")

    settings.CELERY_BROKER_URL = TEST_REDIS_URL
    settings.REDIS_URL = TEST_REDIS_URL

    # Close existing connections so the new broker URL takes full effect.
    celery_app.close()
    celery_app.conf.update(
        broker_url=TEST_REDIS_URL,
        result_backend=TEST_REDIS_URL,
        task_create_missing_queues=True,
    )

    client.flushdb()
    yield
    client.flushdb()
    client.close()


@pytest.fixture()
def redis_client():
    """Isolated Redis handle for queue length assertions."""
    client = redis.Redis.from_url(TEST_REDIS_URL)
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        client.close()


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


@pytest.fixture
def content_svc(session):
    """Provide ContentStorageService with test session."""
    return ContentStorageService(session)


@pytest.fixture
def orchestrator(content_svc):
    """Provide PipelineOrchestrator with real storage service."""
    return PipelineOrchestrator(content_svc)


async def _create_test_content(content_svc: ContentStorageService, suffix: str) -> Content:
    """Create a test content item and return it."""
    raw = RawContentSchema(
        source="rss",
        source_url=f"https://example.com/pipeline-test-{suffix}",
        title=f"Pipeline Test Article {suffix}",
        raw_text="Test content for pipeline integration",
    )
    return await content_svc.store_raw(raw)


async def test_advance_pipeline_gatekeeper_passed_enqueues_understanding(
    orchestrator,
    content_svc,
    redis_client,
):
    """Passing gatekeeper should dispatch next stage to Redis queue."""
    content = await _create_test_content(content_svc, "gatekeeper_pass")
    assert content.pipeline_status == PipelineStatus.fetched

    before = redis_client.llen("pipeline")
    await orchestrator.advance_pipeline(content.id, "gatekeeper", {"passed": True})
    after = redis_client.llen("pipeline")

    assert after == before + 1, (
        f"Expected 'pipeline' queue length {before + 1}, got {after}. "
        f"Redis keys after dispatch: {[k.decode() for k in redis_client.keys('*')]}"
    )
    refreshed = await content_svc.get_by_id(content.id)
    assert refreshed is not None
    assert refreshed.pipeline_status != PipelineStatus.failed


async def test_advance_pipeline_gatekeeper_failed_no_dispatch(orchestrator, content_svc, redis_client):
    """Failing gatekeeper marks failed and should not enqueue next stage."""
    content = await _create_test_content(content_svc, "gatekeeper_fail")
    before = redis_client.llen("pipeline")

    await orchestrator.advance_pipeline(
        content.id,
        "gatekeeper",
        {"passed": False, "reason": "Content does not meet quality threshold"},
    )

    after = redis_client.llen("pipeline")
    assert after == before

    refreshed = await content_svc.get_by_id(content.id)
    assert refreshed is not None
    assert refreshed.pipeline_status == PipelineStatus.failed
    assert refreshed.pipeline_error is not None


async def test_mark_failed_stores_error(orchestrator, content_svc):
    """mark_failed stores failure metadata in JSON format."""
    content = await _create_test_content(content_svc, "mark_failed")

    await orchestrator.mark_failed(content.id, "gatekeeper", "User content detected")

    refreshed = await content_svc.get_by_id(content.id)
    assert refreshed is not None
    assert refreshed.pipeline_status == PipelineStatus.failed
    assert refreshed.pipeline_error is not None

    error_data = json.loads(refreshed.pipeline_error)
    assert error_data["failed_at_stage"] == "gatekeeper"
    assert error_data["failure_reason"] == "User content detected"


async def test_mark_failed_unknown_content(orchestrator):
    """mark_failed on non-existent content_id raises ValueError."""
    with pytest.raises(ValueError, match="Content .* not found"):
        await orchestrator.mark_failed(999999, "scoring", "test")


async def test_advance_pipeline_unknown_stage(orchestrator, content_svc):
    """advance_pipeline with unknown stage raises ValueError."""
    content = await _create_test_content(content_svc, "unknown_stage")

    with pytest.raises(ValueError, match="Unknown stage"):
        await orchestrator.advance_pipeline(content.id, "invalid_stage", {})


async def test_advance_pipeline_understood_enqueues_scoring(orchestrator, content_svc, redis_client):
    """Advancing from understood should enqueue scoring task on Redis."""
    content = await _create_test_content(content_svc, "understood")

    before = redis_client.llen("pipeline")
    await orchestrator.advance_pipeline(content.id, "understood", {})
    after = redis_client.llen("pipeline")

    assert after == before + 1, (
        f"Expected 'pipeline' queue length {before + 1}, got {after}. "
        f"Redis keys after dispatch: {[k.decode() for k in redis_client.keys('*')]}"
    )


async def test_advance_pipeline_indexed_terminal_state(orchestrator, content_svc, redis_client):
    """Indexed is terminal: status updates without enqueueing more tasks."""
    content = await _create_test_content(content_svc, "indexed_terminal")
    await content_svc.update_pipeline_status(content.id, PipelineStatus.scored)

    before = redis_client.llen("pipeline")
    await orchestrator.advance_pipeline(content.id, "indexed", {})
    after = redis_client.llen("pipeline")

    assert after == before
    refreshed = await content_svc.get_by_id(content.id)
    assert refreshed is not None
    assert refreshed.pipeline_status == PipelineStatus.indexed


async def test_content_deleted_after_test(content_svc):
    """Sanity check fixture cleanup mechanics with a regular content insert."""
    raw = RawContentSchema(
        source="rss",
        source_url="https://example.com/cleanup-test",
        title="Cleanup Test",
        raw_text="Should be rolled back",
    )
    content = await content_svc.store_raw(raw)
    assert content.id is not None
