"""Unit tests for RankingService.

TDD: tests written FIRST (RED), then implementation (GREEN).
asyncio_mode = 'auto' — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from alice.models.content import Content, PipelineStatus
from alice.services.ranking import RankingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> MagicMock:
    """Build a MagicMock that looks like a Content ORM object."""
    defaults = dict(
        id=1,
        source="rss",
        quality_score=8.0,
        published_at=datetime.now(UTC) - timedelta(hours=1),
        created_at=datetime.now(UTC) - timedelta(hours=1),
        metadata_={},
        pipeline_status=PipelineStatus.indexed,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Content)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_session():
    """Return a mock AsyncSession."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_scalars_result(items: list) -> MagicMock:
    """Wrap items in scalars().all() mock chain."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


# ---------------------------------------------------------------------------
# compute_p_score tests
# ---------------------------------------------------------------------------


class TestComputePScore:
    def test_compute_p_score_basic(self):
        """quality_score=8.0, RSS source, 1h old → p_score in [0.0, 1.0]."""
        svc = RankingService()
        content = _make_content(quality_score=8.0, source="rss")
        score = svc.compute_p_score(content)
        assert 0.0 <= score <= 1.0

    def test_compute_p_score_no_quality_score(self):
        """quality_score=None → uses 0.5 default for Q_content."""
        svc = RankingService()
        content_none = _make_content(quality_score=None)
        content_half = _make_content(quality_score=5.0)
        now = datetime.now(UTC)
        score_none = svc.compute_p_score(content_none, now=now)
        score_half = svc.compute_p_score(content_half, now=now)
        # Both use Q_content=0.5, same timestamps → equal scores
        assert math.isclose(score_none, score_half, rel_tol=1e-9)

    def test_compute_p_score_high_quality_recent(self):
        """quality_score=10.0 produces higher p_score than quality_score=5.0, same age."""
        svc = RankingService()
        now = datetime.now(UTC)
        pub = now - timedelta(hours=1)
        high = _make_content(quality_score=10.0, published_at=pub)
        low = _make_content(quality_score=5.0, published_at=pub)
        assert svc.compute_p_score(high, now=now) > svc.compute_p_score(low, now=now)

    def test_compute_p_score_time_sensitive_decays_faster(self):
        """arxiv source (24h half-life) decays faster than RSS (168h) at 48h age."""
        svc = RankingService()
        now = datetime.now(UTC)
        pub = now - timedelta(hours=48)
        arxiv = _make_content(quality_score=8.0, source="arxiv", published_at=pub)
        rss = _make_content(quality_score=8.0, source="rss", published_at=pub)
        assert svc.compute_p_score(arxiv, now=now) < svc.compute_p_score(rss, now=now)

    def test_compute_p_score_knowledge_decays_slowly(self):
        """RSS source 7 days old → decay ~0.5 (168h half-life)."""
        svc = RankingService()
        now = datetime.now(UTC)
        pub = now - timedelta(hours=168)
        content = _make_content(quality_score=10.0, source="rss", published_at=pub)
        score = svc.compute_p_score(content, now=now)
        # Q=1.0, decay=0.5^(168/168)=0.5, urgency=1.0 → expected ~0.5
        assert math.isclose(score, 0.5, rel_tol=1e-6)

    def test_compute_p_score_high_urgency_boost(self):
        """metadata_={"urgency": "high"} → p_score *= 1.5 vs no urgency."""
        svc = RankingService()
        now = datetime.now(UTC)
        pub = now - timedelta(hours=1)
        normal = _make_content(quality_score=8.0, published_at=pub, metadata_={})
        urgent = _make_content(quality_score=8.0, published_at=pub, metadata_={"urgency": "high"})
        score_normal = svc.compute_p_score(normal, now=now)
        score_urgent = svc.compute_p_score(urgent, now=now)
        assert math.isclose(score_urgent, score_normal * 1.5, rel_tol=1e-6)

    def test_compute_p_score_no_published_at_uses_created_at(self):
        """published_at=None, created_at=1h ago → decay computed from created_at."""
        svc = RankingService()
        now = datetime.now(UTC)
        created = now - timedelta(hours=1)
        content = _make_content(quality_score=8.0, published_at=None, created_at=created)
        score = svc.compute_p_score(content, now=now)
        assert 0.0 < score <= 2.0

    def test_compute_p_score_no_timestamps(self):
        """published_at=None, created_at=None → decay=1.0 (fresh assumed)."""
        svc = RankingService()
        now = datetime.now(UTC)
        content = _make_content(quality_score=8.0, published_at=None, created_at=None)
        score = svc.compute_p_score(content, now=now)
        # Q=0.8, decay=1.0, urgency=1.0 → 0.8
        assert math.isclose(score, 0.8, rel_tol=1e-9)

    def test_compute_p_score_future_dated(self):
        """published_at 1 hour in future → age clamped to 0 → decay=1.0."""
        svc = RankingService()
        now = datetime.now(UTC)
        future_pub = now + timedelta(hours=1)
        content = _make_content(quality_score=8.0, published_at=future_pub)
        score = svc.compute_p_score(content, now=now)
        # age=0 → decay=1.0 → score=0.8
        assert math.isclose(score, 0.8, rel_tol=1e-9)

    def test_compute_p_score_clamped_to_max(self):
        """Extremely high urgency + perfect quality → result ≤ 2.0."""
        svc = RankingService()
        now = datetime.now(UTC)
        pub = now - timedelta(seconds=1)  # near-zero age → decay~1.0
        content = _make_content(quality_score=10.0, published_at=pub, metadata_={"urgency": "high"})
        score = svc.compute_p_score(content, now=now)
        assert score <= 2.0


# ---------------------------------------------------------------------------
# _is_time_sensitive tests
# ---------------------------------------------------------------------------


class TestIsTimeSensitive:
    def test_is_time_sensitive_arxiv(self):
        """source='arxiv' → True."""
        svc = RankingService()
        content = _make_content(source="arxiv", metadata_={})
        assert svc._is_time_sensitive(content) is True

    def test_is_time_sensitive_news_metadata(self):
        """metadata_={"content_type": "news"} → True."""
        svc = RankingService()
        content = _make_content(source="rss", metadata_={"content_type": "news"})
        assert svc._is_time_sensitive(content) is True

    def test_is_time_sensitive_rss_default(self):
        """source='rss', no metadata content_type → False."""
        svc = RankingService()
        content = _make_content(source="rss", metadata_={})
        assert svc._is_time_sensitive(content) is False


# ---------------------------------------------------------------------------
# async method tests
# ---------------------------------------------------------------------------


class TestUpdatePScore:
    async def test_update_p_score_persists(self):
        """update_p_score sets content.p_score and returns float."""
        svc = RankingService()
        session = _make_session()
        now = datetime.now(UTC)
        pub = now - timedelta(hours=1)
        content = _make_content(quality_score=8.0, published_at=pub)

        result = await svc.update_p_score(session, content)

        assert isinstance(result, float)
        assert 0.0 <= result <= 2.0
        # Verify p_score was assigned on the content object
        assert content.p_score == result


class TestBatchUpdatePScores:
    async def test_batch_update_p_scores_returns_count(self):
        """batch_update_p_scores updates all items and returns count."""
        svc = RankingService()
        session = _make_session()

        content_items = [MagicMock(spec=Content) for _ in range(3)]
        for c in content_items:
            c.quality_score = 7.0
            c.source = "rss"
            c.published_at = datetime.now(UTC) - timedelta(hours=2)
            c.created_at = datetime.now(UTC) - timedelta(hours=2)
            c.metadata_ = {}
            c.pipeline_status = PipelineStatus.indexed

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = content_items
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        count = await svc.batch_update_p_scores(session, limit=10)

        assert count == 3
        session.commit.assert_called_once()
