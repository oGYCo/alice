"""Unit tests for DB-driven Celery Beat scheduler.

Tests get_dynamic_schedule() — no real DB, broker, or LLM required.
asyncio_mode = 'auto' in pyproject.toml → no @pytest.mark.asyncio needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from alice.models.source import Source, SourceType
from alice.pipeline.scheduler import BEAT_SCHEDULE, get_beat_schedule, get_dynamic_schedule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(**kwargs) -> MagicMock:
    """Create a mock Source ORM object."""
    defaults = dict(
        id=1,
        name="Test RSS",
        type=SourceType.rss,
        url="https://example.com/feed.xml",
        config={},
        is_active=True,
        fetch_interval_minutes=30,
        last_fetched_at=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Source)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ---------------------------------------------------------------------------
# Static schedule (backward-compat)
# ---------------------------------------------------------------------------


class TestStaticBeatSchedule:
    def test_beat_schedule_has_fetch_all_sources(self):
        """BEAT_SCHEDULE must include the static fetch-all-sources entry."""
        assert "fetch-all-sources" in BEAT_SCHEDULE

    def test_beat_schedule_fetch_interval_is_1800(self):
        """fetch-all-sources schedule should be 1800.0 seconds (30 min)."""
        assert BEAT_SCHEDULE["fetch-all-sources"]["schedule"] == 1800.0

    def test_beat_schedule_has_retry_failed(self):
        """BEAT_SCHEDULE must include retry-failed-content entry."""
        assert "retry-failed-content" in BEAT_SCHEDULE

    def test_beat_schedule_retry_failed_is_6_hours(self):
        """retry-failed-content schedule should be 21600.0 seconds (6 hours)."""
        assert BEAT_SCHEDULE["retry-failed-content"]["schedule"] == 21600.0

    def test_beat_schedule_has_batch_p_scores(self):
        """BEAT_SCHEDULE must include batch-update-p-scores-daily entry."""
        assert "batch-update-p-scores-daily" in BEAT_SCHEDULE

    def test_beat_schedule_batch_p_scores_is_daily(self):
        """batch-update-p-scores-daily schedule should be 86400.0 seconds (24h)."""
        assert BEAT_SCHEDULE["batch-update-p-scores-daily"]["schedule"] == 86400.0

    def test_beat_schedule_has_schedule_push_batches(self):
        """BEAT_SCHEDULE must include schedule-push-batches entry."""
        assert "schedule-push-batches" in BEAT_SCHEDULE

    def test_beat_schedule_push_batches_is_20_minutes(self):
        """schedule-push-batches schedule should be 1200.0 seconds (20 min)."""
        assert BEAT_SCHEDULE["schedule-push-batches"]["schedule"] == 1200.0

    def test_get_beat_schedule_returns_dict(self):
        """get_beat_schedule() returns the static schedule dict."""
        schedule = get_beat_schedule()
        assert isinstance(schedule, dict)
        assert "fetch-all-sources" in schedule
        assert "retry-failed-content" in schedule
        assert "batch-update-p-scores-daily" in schedule
        assert "schedule-push-batches" in schedule


# ---------------------------------------------------------------------------
# get_dynamic_schedule
# ---------------------------------------------------------------------------


class TestGetDynamicSchedule:
    async def test_dynamic_schedule_includes_static_entries(self):
        """get_dynamic_schedule() always includes fallback static entries."""
        session = AsyncMock()
        # No active sources
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute.return_value = result

        schedule = await get_dynamic_schedule(session)

        assert "fetch-all-sources" in schedule
        assert "retry-failed-content" in schedule

    async def test_dynamic_schedule_adds_per_source_entries(self):
        """Each active source gets its own Beat entry."""
        session = AsyncMock()
        sources = [
            _make_source(id=1, name="RSS A", fetch_interval_minutes=15),
            _make_source(id=2, name="arXiv B", fetch_interval_minutes=60, type=SourceType.arxiv),
        ]
        result = MagicMock()
        result.scalars.return_value.all.return_value = sources
        session.execute.return_value = result

        schedule = await get_dynamic_schedule(session)

        assert "fetch-source-1" in schedule
        assert "fetch-source-2" in schedule

    async def test_dynamic_schedule_source_entry_has_correct_task(self):
        """Per-source Beat entry uses the fetch task."""
        session = AsyncMock()
        sources = [_make_source(id=3, fetch_interval_minutes=30)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = sources
        session.execute.return_value = result

        schedule = await get_dynamic_schedule(session)
        entry = schedule["fetch-source-3"]

        assert "task" in entry
        assert "fetch" in entry["task"].lower() or "source" in entry["task"].lower()

    async def test_dynamic_schedule_interval_includes_base_minutes(self):
        """Per-source schedule interval is >= fetch_interval_minutes * 60 seconds."""
        session = AsyncMock()
        sources = [_make_source(id=4, fetch_interval_minutes=20)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = sources
        session.execute.return_value = result

        # Patch random.randint to return 0 (no jitter)
        with patch("alice.pipeline.scheduler.random.randint", return_value=0):
            schedule = await get_dynamic_schedule(session)

        entry = schedule["fetch-source-4"]
        # With 0 jitter: exactly 20 * 60 = 1200 seconds
        assert entry["schedule"] == 1200.0

    async def test_dynamic_schedule_applies_jitter(self):
        """Per-source schedule adds jitter (0-5 minutes = 0-300 seconds)."""
        session = AsyncMock()
        sources = [_make_source(id=5, fetch_interval_minutes=30)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = sources
        session.execute.return_value = result

        with patch("alice.pipeline.scheduler.random.randint", return_value=3):
            schedule = await get_dynamic_schedule(session)

        entry = schedule["fetch-source-5"]
        # 30 * 60 + 3 * 60 = 1980
        assert entry["schedule"] == 1980.0

    async def test_dynamic_schedule_empty_sources_only_static(self):
        """With no active sources, schedule contains only static entries."""
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute.return_value = result

        schedule = await get_dynamic_schedule(session)

        # 4 static entries: fetch-all-sources, retry-failed-content,
        # batch-update-p-scores-daily, schedule-push-batches
        assert len(schedule) == 4

    async def test_dynamic_schedule_source_entry_has_kwargs_with_source_id(self):
        """Per-source entry includes kwargs with source_id."""
        session = AsyncMock()
        sources = [_make_source(id=7, fetch_interval_minutes=30)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = sources
        session.execute.return_value = result

        schedule = await get_dynamic_schedule(session)
        entry = schedule["fetch-source-7"]

        assert "kwargs" in entry
        assert entry["kwargs"].get("source_id") == 7
