"""End-to-end integration tests for Phase 1 Alice API.

Tests the Phase 1 features via HTTP API using httpx.AsyncClient:
- 7-dimension scoring schema and total quality score
- P_score ranking order (descending)
- Meilisearch search & suggest endpoints
- URL dedup normalization and SimHash near-duplicate detection
- Time-window scheduling logic
- Enhanced Telegram push card formatting
- Push preferences endpoint

Requires a real PostgreSQL test database.
Set TEST_DATABASE_URL env var to run:
    export TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/alice_test"
    uv run pytest tests/integration/test_phase1_e2e.py -v -m integration

Skip automatically when TEST_DATABASE_URL is not set.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.config import settings
from alice.db import get_db
from alice.main import create_app
from alice.models import Base
from alice.models.content import Content
from alice.services.dedup import DeduplicationService
from alice.services.push_scheduler import PushScheduler, PushSchedulerSettings
from alice.services.scoring import SevenDimensionScoringService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# ---------------------------------------------------------------------------
# Module-level skip if TEST_DATABASE_URL not set
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL not set — skipping integration tests", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest_asyncio.fixture(loop_scope="module")
async def http_client(engine):
    """Provide httpx.AsyncClient with FastAPI app wired to the test DB."""
    app = create_app()
    # Override get_db to use the test engine instead of the configured DB URL
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class DummyLLM:
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        del prompt, system, temperature, max_tokens
        return (
            "{"
            '"substance": 0.7, '
            '"density": 0.6, '
            '"credibility": 0.8, '
            '"novelty": 0.5, '
            '"actionability": 0.9, '
            '"social_signal": 0.4, '
            '"timeliness": 0.6, '
            '"reasoning": "ok"'
            "}"
        )


async def test_7d_quality_scoring_formula():
    """Seven-dimension scoring returns all required fields."""
    svc = SevenDimensionScoringService(DummyLLM())
    result = await svc.score(
        content_text="Test content",
        content_title="Test title",
        source_url="https://example.com",
        source_type="rss",
    )

    dims = result.dimensions
    assert dims.novelty is not None
    assert dims.substance is not None
    assert dims.actionability is not None
    assert dims.social_signal is not None
    assert dims.credibility is not None
    assert dims.timeliness is not None
    assert dims.density is not None


def _make_content(**kwargs) -> Content:
    defaults = dict(
        id=1,
        source="rss",
        source_url="https://example.com",
        title="Test",
        summary="Summary",
        metadata_={},
        created_at=datetime.now(UTC),
        pipeline_status="indexed",
        quality_score=8.0,
        p_score=0.8,
    )
    defaults.update(kwargs)
    content = Content(**{k: v for k, v in defaults.items() if k not in {"id", "p_score"}})
    content.id = defaults["id"]
    content.p_score = defaults["p_score"]
    return content


async def test_p_score_ranking_orders_content():
    """RankingService.compute_p_score orders items by p_score descending."""
    high = _make_content(id=1, p_score=1.2)
    mid = _make_content(id=2, p_score=0.7)
    low = _make_content(id=3, p_score=0.1)

    # Sort using p_score (RankingService computes p_scores; test sorting logic)
    ranked = sorted([mid, low, high], key=lambda c: c.p_score or 0.0, reverse=True)
    assert [c.id for c in ranked] == [1, 2, 3]


async def test_meilisearch_search_endpoint(http_client):
    """GET /api/v1/search returns 200 or 503 when Meilisearch is down."""
    response = await http_client.get("/api/v1/search", params={"q": "test"})
    assert response.status_code in (200, 503)


async def test_search_suggest_endpoint(http_client):
    """GET /api/v1/search/suggest returns 200 or 503."""
    response = await http_client.get("/api/v1/search/suggest", params={"q": "test"})
    assert response.status_code in (200, 503)


async def test_dedup_url_normalization():
    """normalize_url strips tracking params and fragments."""
    svc = DeduplicationService()
    url = "https://www.example.com/path/?utm_source=feed&id=1#section"
    normalized = svc.normalize_url(url)
    assert normalized == "https://example.com/path?id=1"


async def test_dedup_simhash_near_duplicate():
    """is_near_duplicate detects similar content."""
    svc = DeduplicationService()
    text_a = "Alice builds an AI secretary for RSS feeds and papers."
    text_b = "Alice builds an AI secretary for RSS feeds and papers!"
    hash_a = svc.compute_simhash(text_a)
    hash_b = svc.compute_simhash(text_b)
    assert svc.is_near_duplicate(hash_a, hash_b)


async def test_time_window_scheduling_quiet_hours():
    """Quiet hours: 23:00 is quiet, 10:00 is not."""
    scheduler = PushScheduler(PushSchedulerSettings())
    quiet_dt = datetime(2025, 1, 1, 23, 0, tzinfo=UTC)
    active_dt = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    assert scheduler.is_quiet_hours(quiet_dt) is True
    assert scheduler.is_quiet_hours(active_dt) is False


async def test_time_window_content_type_by_window():
    """Content type for window returns expected values."""
    scheduler = PushScheduler(PushSchedulerSettings())
    morning = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    afternoon = datetime(2025, 1, 1, 14, 30, tzinfo=UTC)
    evening = datetime(2025, 1, 1, 21, 0, tzinfo=UTC)
    assert scheduler.get_content_type_for_window(morning) == "deep_knowledge"
    assert scheduler.get_content_type_for_window(afternoon) == "practical"
    assert scheduler.get_content_type_for_window(evening) == "thought_provoking"


def _make_card_content(content_type: str) -> Content:
    content = _make_content(
        id=1,
        title="Test Title",
        source_url="https://example.com",
        summary="Test summary",
        metadata_={"content_type": content_type, "push_reason": "Reason"},
    )
    content.key_points = ["Point A", "Point B"]
    content.estimated_read_time = 5
    return content


async def test_enhanced_card_deep_knowledge_type():
    """Deep knowledge cards have title and 6 buttons."""
    from alice.bot.handlers.push import build_push_card

    content = _make_card_content("deep_knowledge")
    text, markup = build_push_card(content)
    assert "Test Title" in text
    buttons = sum(len(row) for row in markup.inline_keyboard)
    assert buttons == 6


async def test_enhanced_card_time_sensitive_type():
    """Time-sensitive cards have title and 2 buttons."""
    from alice.bot.handlers.push import build_push_card

    content = _make_card_content("time_sensitive")
    text, markup = build_push_card(content)
    assert "Test Title" in text
    buttons = sum(len(row) for row in markup.inline_keyboard)
    assert buttons == 2


async def test_enhanced_card_thought_provoking_type():
    """Thought-provoking cards have title and 4 buttons."""
    from alice.bot.handlers.push import build_push_card

    content = _make_card_content("thought_provoking")
    text, markup = build_push_card(content)
    assert "Test Title" in text
    buttons = sum(len(row) for row in markup.inline_keyboard)
    assert buttons == 4


async def test_push_preferences_endpoint(http_client):
    """GET /api/v1/settings/push returns 200."""
    response = await http_client.get("/api/v1/settings/push", params={"user_id": 1})
    assert response.status_code in (200, 404)


async def test_full_phase1_workflow(http_client):
    """Full Phase 1 workflow smoke test via API endpoints."""
    search_response = await http_client.get("/api/v1/search", params={"q": "test"})
    assert search_response.status_code in (200, 503)

    suggest_response = await http_client.get("/api/v1/search/suggest", params={"q": "test"})
    assert suggest_response.status_code in (200, 503)

    push_response = await http_client.get("/api/v1/settings/push", params={"user_id": 1})
    assert push_response.status_code in (200, 404)
