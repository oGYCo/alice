"""Integration tests for ContentStorageService and SourceService.

Runs against real PostgreSQL from docker-compose.yml (localhost:5432, database: alice_test).
Override with TEST_DATABASE_URL env var if needed.

    uv run pytest tests/integration/test_storage_db.py -v -m integration
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.models import Base
from alice.models.content import PipelineStatus
from alice.schemas.content import RawContentSchema
from alice.schemas.source import SourceConfigSchema
from alice.services.source_service import SourceService
from alice.services.storage import ContentStorageService

from .conftest import ensure_test_database, get_test_database_url

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ensure_test_database()
TEST_DATABASE_URL = get_test_database_url()


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
    """Provide a session with savepoint isolation.

    Services may call session.commit(); join_transaction_mode='create_savepoint'
    converts those commits into SAVEPOINT releases instead of real commits.
    The outer transaction is rolled back after each test.
    """
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
    return ContentStorageService(session)


@pytest.fixture
def source_svc(session):
    return SourceService(session)


# ---------------------------------------------------------------------------
# ContentStorageService integration tests
# ---------------------------------------------------------------------------


async def test_store_raw_roundtrip(content_svc):
    """store_raw → get_by_id roundtrip."""
    raw = RawContentSchema(
        source="rss",
        source_url="https://example.com/integration-test-article",
        title="Integration Test Article",
        raw_text="Some content here",
    )
    content = await content_svc.store_raw(raw)
    assert content.id is not None
    assert content.pipeline_status == PipelineStatus.fetched

    fetched = await content_svc.get_by_id(content.id)
    assert fetched is not None
    assert fetched.title == "Integration Test Article"


async def test_store_raw_dedup_integration(content_svc):
    """Inserting same URL twice returns same record (dedup)."""
    raw = RawContentSchema(
        source="rss",
        source_url="https://example.com/dedup-test",
    )
    first = await content_svc.store_raw(raw)
    second = await content_svc.store_raw(raw)
    assert first.id == second.id


async def test_update_pipeline_status_integration(content_svc):
    """update_pipeline_status persists to DB."""
    raw = RawContentSchema(source="rss", source_url="https://example.com/status-test")
    content = await content_svc.store_raw(raw)

    await content_svc.update_pipeline_status(content.id, PipelineStatus.gatekept)
    refreshed = await content_svc.get_by_id(content.id)
    assert refreshed.pipeline_status == PipelineStatus.gatekept


async def test_get_pending_integration(content_svc):
    """get_pending returns items at specified stage."""
    raw = RawContentSchema(source="rss", source_url="https://example.com/pending-test")
    content = await content_svc.store_raw(raw)

    pending = await content_svc.get_pending(PipelineStatus.fetched)
    ids = [c.id for c in pending]
    assert content.id in ids


async def test_get_pushable_integration(content_svc):
    """get_pushable returns scored content above threshold."""
    raw = RawContentSchema(source="rss", source_url="https://example.com/pushable-test")
    content = await content_svc.store_raw(raw)
    await content_svc.update_score(content.id, score=8.0, reasoning="High quality")

    pushable = await content_svc.get_pushable(min_score=6.0)
    ids = [c.id for c in pushable]
    assert content.id in ids


# ---------------------------------------------------------------------------
# SourceService integration tests
# ---------------------------------------------------------------------------


async def test_create_source_integration(source_svc):
    """create → list_active roundtrip."""
    config = SourceConfigSchema(
        name="Integration RSS Feed",
        url="https://example.com/integration.xml",
        type="rss",
    )
    source = await source_svc.create(config)
    assert source.id is not None
    assert source.is_active is True

    active = await source_svc.list_active()
    ids = [s.id for s in active]
    assert source.id in ids


async def test_mark_fetched_integration(source_svc):
    """mark_fetched sets last_fetched_at timestamp."""
    config = SourceConfigSchema(
        name="Fetch Test Feed",
        url="https://example.com/fetch-test.xml",
        type="rss",
    )
    source = await source_svc.create(config)
    assert source.last_fetched_at is None

    await source_svc.mark_fetched(source.id)

    active = await source_svc.list_active()
    updated = next(s for s in active if s.id == source.id)
    assert updated.last_fetched_at is not None
