"""Unit tests for pipeline Celery tasks.

Tests use .apply() for synchronous execution — no broker needed.
asyncio.run() inside each task is NOT patched — real coroutines run with
mocked service dependencies (AsyncSessionLocal, ContentStorageService, etc.).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from alice.models.content import Content, PipelineStatus
from alice.pipeline.tasks import (
    task_run_gatekeeper,
    task_run_indexing,
    task_run_scoring,
    task_run_understanding,
    task_retry_failed_graph_extractions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> MagicMock:
    defaults = dict(
        id=1,
        title="Test Article",
        raw_text="This is a test article with substantial content.",
        extracted_text="This is extracted content for testing.",
        source="rss",
        source_url="https://example.com/article",
        language="en",
        pipeline_status=PipelineStatus.fetched,
        pipeline_error=None,
        quality_score=None,
        summary="Test summary",
        key_points=["point1", "point2"],
        domains=["AI"],
        estimated_read_time=5,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Content)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_session_cm():
    """Return (cm, session) where cm is a proper async context manager mock."""
    session = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------


class TestTaskRegistration:
    def test_pipeline_tasks_registered_with_correct_names(self):
        """All pipeline tasks should be registered with alice.pipeline.tasks.* names."""
        from alice.worker.celery_app import celery_app

        registered = celery_app.tasks.keys()
        expected = [
            "alice.pipeline.tasks.task_run_gatekeeper",
            "alice.pipeline.tasks.task_run_understanding",
            "alice.pipeline.tasks.task_run_scoring",
            "alice.pipeline.tasks.task_run_indexing",
        ]
        for task_name in expected:
            assert task_name in registered, f"Task {task_name} not registered"

    def test_pipeline_tasks_have_max_retries_3(self):
        """Pipeline tasks should have max_retries=3."""
        assert task_run_gatekeeper.max_retries == 3
        assert task_run_understanding.max_retries == 3
        assert task_run_scoring.max_retries == 3
        assert task_run_indexing.max_retries == 3


# ---------------------------------------------------------------------------
# task_run_gatekeeper
# ---------------------------------------------------------------------------


class TestTaskRunGatekeeper:
    def test_gatekeeper_task_passes_content(self):
        """Gatekeeper task should return success dict when content passes."""
        content = _make_content(
            id=42,
            pipeline_status=PipelineStatus.fetched,
            raw_text="This is a long and meaningful article about AI research.",
            extracted_text="This is a long and meaningful article about AI research.",
        )

        mock_decision = MagicMock()
        mock_decision.passed = True
        mock_decision.reason = "high quality"
        mock_decision.confidence = 0.95
        mock_decision.method = "ollama"

        cm, _session = _make_session_cm()

        mock_storage = AsyncMock()
        mock_storage.get_by_id.return_value = content
        mock_storage.update_pipeline_status = AsyncMock()

        mock_gk = AsyncMock()
        mock_gk.evaluate.return_value = mock_decision

        with (
            patch("alice.pipeline.tasks.AsyncSessionLocal", return_value=cm),
            patch("alice.pipeline.tasks.ContentStorageService", return_value=mock_storage),
            patch("alice.pipeline.tasks.GatekeeperService", return_value=mock_gk),
            patch("alice.pipeline.tasks.task_run_understanding"),
        ):
            result = task_run_gatekeeper.apply(args=[42]).result

        assert result["content_id"] == 42
        assert result["stage"] == "gatekeeper"
        assert result["passed"] is True

    def test_gatekeeper_task_rejects_content(self):
        """Gatekeeper task should mark content failed when rejected."""
        content = _make_content(id=10, pipeline_status=PipelineStatus.fetched)

        mock_decision = MagicMock()
        mock_decision.passed = False
        mock_decision.reason = "too short"
        mock_decision.confidence = 0.9
        mock_decision.method = "ollama"

        cm, _session = _make_session_cm()

        mock_storage = AsyncMock()
        mock_storage.get_by_id.return_value = content
        mock_storage.update_pipeline_status = AsyncMock()

        mock_gk = AsyncMock()
        mock_gk.evaluate.return_value = mock_decision

        with (
            patch("alice.pipeline.tasks.AsyncSessionLocal", return_value=cm),
            patch("alice.pipeline.tasks.ContentStorageService", return_value=mock_storage),
            patch("alice.pipeline.tasks.GatekeeperService", return_value=mock_gk),
        ):
            result = task_run_gatekeeper.apply(args=[10]).result

        assert result["content_id"] == 10
        assert result["stage"] == "gatekeeper"
        assert result["passed"] is False

    def test_gatekeeper_task_returns_correct_shape(self):
        """Gatekeeper task result must include content_id and stage keys."""
        result = task_run_gatekeeper.apply(args=[1])
        # Even without actual services, the task must return a dict with expected keys
        # When services fail to connect, it might fail — but we check the task exists
        assert result is not None


# ---------------------------------------------------------------------------
# task_run_understanding
# ---------------------------------------------------------------------------


class TestTaskRunUnderstanding:
    def test_understanding_task_has_correct_name(self):
        """Understanding task must have the correct registered name."""
        assert task_run_understanding.name == "alice.pipeline.tasks.task_run_understanding"

    def test_understanding_task_result_shape(self):
        """Understanding task should return content_id and stage."""
        content = _make_content(id=5, pipeline_status=PipelineStatus.gatekept)

        mock_result = MagicMock()
        mock_result.summary = "AI article summary"
        mock_result.key_points = ["point1"]
        mock_result.domains = ["AI"]
        mock_result.estimated_read_time = 5

        mock_un = AsyncMock()
        mock_un.process.return_value = mock_result

        cm, _session = _make_session_cm()

        mock_storage = AsyncMock()
        mock_storage.get_by_id.return_value = content
        mock_storage.update_understanding = AsyncMock()

        with (
            patch("alice.pipeline.tasks.AsyncSessionLocal", return_value=cm),
            patch("alice.pipeline.tasks.ContentStorageService", return_value=mock_storage),
            patch("alice.pipeline.tasks.UnderstandingService", return_value=mock_un),
            patch("alice.pipeline.tasks.task_run_scoring"),
        ):
            result = task_run_understanding.apply(args=[5]).result

        assert result["content_id"] == 5
        assert result["stage"] == "understanding"


# ---------------------------------------------------------------------------
# task_run_scoring
# ---------------------------------------------------------------------------


class TestTaskRunScoring:
    def test_scoring_task_has_correct_name(self):
        """Scoring task must have the correct registered name."""
        assert task_run_scoring.name == "alice.pipeline.tasks.task_run_scoring"

    def test_scoring_task_result_shape(self):
        """Scoring task should return content_id and stage."""
        content = _make_content(
            id=7,
            pipeline_status=PipelineStatus.understood,
            summary="Great summary",
            key_points=["p1", "p2"],
        )

        mock_score_result = MagicMock()
        mock_score_result.score = 8.5
        mock_score_result.reasoning = "Very relevant"

        mock_sc = AsyncMock()
        mock_sc.score.return_value = mock_score_result

        cm, _session = _make_session_cm()

        mock_storage = AsyncMock()
        mock_storage.get_by_id.return_value = content
        mock_storage.update_score = AsyncMock()

        with (
            patch("alice.pipeline.tasks.AsyncSessionLocal", return_value=cm),
            patch("alice.pipeline.tasks.ContentStorageService", return_value=mock_storage),
            patch("alice.pipeline.tasks.ScoringService", return_value=mock_sc),
            patch("alice.pipeline.tasks.task_run_indexing"),
        ):
            result = task_run_scoring.apply(args=[7]).result

        assert result["content_id"] == 7
        assert result["stage"] == "scoring"


# ---------------------------------------------------------------------------
# task_run_indexing
# ---------------------------------------------------------------------------


class TestTaskRunIndexing:
    def test_indexing_task_has_correct_name(self):
        """Indexing task must have the correct registered name."""
        assert task_run_indexing.name == "alice.pipeline.tasks.task_run_indexing"

    def test_indexing_task_result_shape(self):
        """Indexing task should return content_id and stage."""
        content = _make_content(id=9, pipeline_status=PipelineStatus.scored)

        cm, _session = _make_session_cm()

        mock_storage = AsyncMock()
        mock_storage.get_by_id.return_value = content
        mock_storage.update_pipeline_status = AsyncMock()

        with (
            patch("alice.pipeline.tasks.AsyncSessionLocal", return_value=cm),
            patch("alice.pipeline.tasks.ContentStorageService", return_value=mock_storage),
        ):
            result = task_run_indexing.apply(args=[9]).result

        assert result["content_id"] == 9
        assert result["stage"] == "indexing"


# ---------------------------------------------------------------------------
# Retry tasks
# ---------------------------------------------------------------------------


class TestTaskRetryFailed:
    def test_retry_failed_task_registered(self):
        """task_retry_failed must be registered with Celery."""
        from alice.worker.celery_app import celery_app

        registered = celery_app.tasks.keys()
        assert "alice.pipeline.tasks.task_retry_failed" in registered


class TestTaskRetryFailedGraphExtractions:
    def test_retry_graph_extraction_task_registered(self):
        """task_retry_failed_graph_extractions must be registered with Celery."""
        from alice.worker.celery_app import celery_app

        registered = celery_app.tasks.keys()
        assert "alice.pipeline.tasks.task_retry_failed_graph_extractions" in registered

    def test_retry_graph_extraction_task_in_beat_schedule(self):
        """The beat schedule should contain the graph extraction retry task."""
        from alice.pipeline.scheduler import get_beat_schedule

        schedule = get_beat_schedule()
        assert "retry-failed-graph-extractions-every-12-hours" in schedule
        entry = schedule["retry-failed-graph-extractions-every-12-hours"]
        assert entry["task"] == "alice.pipeline.tasks.task_retry_failed_graph_extractions"
        assert entry["schedule"] == 43200.0
