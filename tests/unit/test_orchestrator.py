"""Unit tests for PipelineOrchestrator state machine.

Uses AsyncMock for DB session — no real DB, broker, or LLM required.
asyncio_mode = 'auto' in pyproject.toml → no @pytest.mark.asyncio decorator.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alice.models.content import Content, PipelineStatus
from alice.pipeline.orchestrator import PipelineOrchestrator
from alice.services.storage import ContentStorageService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> MagicMock:
    defaults = dict(
        id=1,
        title="Test Article",
        raw_text="Some text content here",
        extracted_text="Extracted content",
        source="rss",
        source_url="https://example.com/article",
        pipeline_status=PipelineStatus.fetched,
        pipeline_error=None,
        quality_score=None,
        summary=None,
        key_points=None,
        domains=None,
        estimated_read_time=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Content)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_storage(content: MagicMock | None = None) -> AsyncMock:
    storage = AsyncMock(spec=ContentStorageService)
    if content is not None:
        storage.get_by_id.return_value = content
    return storage


# ---------------------------------------------------------------------------
# PipelineOrchestrator.process_new_content
# ---------------------------------------------------------------------------


class TestProcessNewContent:
    async def test_process_new_content_dispatches_gatekeeper(self):
        """process_new_content should dispatch task_run_gatekeeper for fetched content."""
        content = _make_content(id=42, pipeline_status=PipelineStatus.fetched)
        storage = _make_storage(content)

        with patch("alice.pipeline.tasks.task_run_gatekeeper") as mock_task:
            orchestrator = PipelineOrchestrator(storage)
            await orchestrator.process_new_content(42)

        mock_task.delay.assert_called_once_with(42)

    async def test_process_new_content_raises_on_wrong_status(self):
        """If content is not in 'fetched' state, raise ValueError."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.gatekept)
        storage = _make_storage(content)

        orchestrator = PipelineOrchestrator(storage)
        with pytest.raises(ValueError, match="Expected status 'fetched'"):
            await orchestrator.process_new_content(1)

    async def test_process_new_content_raises_on_missing_content(self):
        """If content not found, raise ValueError."""
        storage = AsyncMock(spec=ContentStorageService)
        storage.get_by_id.return_value = None

        orchestrator = PipelineOrchestrator(storage)
        with pytest.raises(ValueError, match="Content.*not found"):
            await orchestrator.process_new_content(999)


# ---------------------------------------------------------------------------
# PipelineOrchestrator.advance_pipeline
# ---------------------------------------------------------------------------


class TestAdvancePipeline:
    async def test_advance_from_gatekept_dispatches_understanding(self):
        """After gatekeeper passes, dispatch task_run_understanding."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.gatekept)
        storage = _make_storage(content)

        with patch("alice.pipeline.tasks.task_run_understanding") as mock_task:
            orchestrator = PipelineOrchestrator(storage)
            await orchestrator.advance_pipeline(1, "gatekept", {"passed": True})

        mock_task.delay.assert_called_once_with(1)

    async def test_advance_from_understood_dispatches_scoring(self):
        """After understanding, dispatch task_run_scoring."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.understood)
        storage = _make_storage(content)

        with patch("alice.pipeline.tasks.task_run_scoring") as mock_task:
            orchestrator = PipelineOrchestrator(storage)
            await orchestrator.advance_pipeline(1, "understood", {"summary": "Test"})

        mock_task.delay.assert_called_once_with(1)

    async def test_advance_from_scored_dispatches_indexing(self):
        """After scoring, dispatch task_run_indexing."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.scored)
        storage = _make_storage(content)

        with patch("alice.pipeline.tasks.task_run_indexing") as mock_task:
            orchestrator = PipelineOrchestrator(storage)
            await orchestrator.advance_pipeline(1, "scored", {"score": 8.5})

        mock_task.delay.assert_called_once_with(1)

    async def test_advance_from_indexed_does_not_dispatch(self):
        """After indexing (terminal stage), no further task dispatched."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.indexed)
        storage = _make_storage(content)

        with (
            patch("alice.pipeline.tasks.task_run_gatekeeper") as gk,
            patch("alice.pipeline.tasks.task_run_understanding") as un,
            patch("alice.pipeline.tasks.task_run_scoring") as sc,
            patch("alice.pipeline.tasks.task_run_indexing") as ix,
        ):
            orchestrator = PipelineOrchestrator(storage)
            await orchestrator.advance_pipeline(1, "indexed", {})

        gk.delay.assert_not_called()
        un.delay.assert_not_called()
        sc.delay.assert_not_called()
        ix.delay.assert_not_called()

    async def test_advance_gatekeeper_failed_sets_status_failed(self):
        """Gatekeeper rejection sets status=failed with error details."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.fetched)
        storage = _make_storage(content)

        orchestrator = PipelineOrchestrator(storage)
        await orchestrator.advance_pipeline(
            1,
            "gatekeeper",
            {"passed": False, "reason": "too short"},
        )

        storage.update_pipeline_status.assert_called_once()
        call_kwargs = storage.update_pipeline_status.call_args
        assert call_kwargs[0][1] == PipelineStatus.failed
        error_json = call_kwargs[1].get("error") or call_kwargs[0][2]
        error_data = json.loads(error_json)
        assert error_data["failed_at_stage"] == "gatekeeper"
        assert "failure_reason" in error_data

    async def test_advance_unknown_stage_raises(self):
        """Unknown stage name should raise ValueError."""
        content = _make_content(id=1, pipeline_status=PipelineStatus.fetched)
        storage = _make_storage(content)

        orchestrator = PipelineOrchestrator(storage)
        with pytest.raises(ValueError, match="Unknown stage"):
            await orchestrator.advance_pipeline(1, "unknown_stage", {})

    async def test_advance_pipeline_raises_on_missing_content(self):
        """advance_pipeline raises ValueError if content not found."""
        storage = AsyncMock(spec=ContentStorageService)
        storage.get_by_id.return_value = None

        orchestrator = PipelineOrchestrator(storage)
        with pytest.raises(ValueError, match="Content.*not found"):
            await orchestrator.advance_pipeline(999, "gatekept", {})


# ---------------------------------------------------------------------------
# PipelineOrchestrator.mark_failed
# ---------------------------------------------------------------------------


class TestMarkFailed:
    async def test_mark_failed_stores_error_json(self):
        """mark_failed stores JSON with failure_reason and failed_at_stage."""
        content = _make_content(id=1)
        storage = _make_storage(content)

        orchestrator = PipelineOrchestrator(storage)
        await orchestrator.mark_failed(1, stage="gatekeeper", reason="API error")

        storage.update_pipeline_status.assert_called_once()
        call_args = storage.update_pipeline_status.call_args
        assert call_args[0][1] == PipelineStatus.failed
        # error argument is a JSON string
        error_arg = call_args[1].get("error") or call_args[0][2]
        error_data = json.loads(error_arg)
        assert error_data["failure_reason"] == "API error"
        assert error_data["failed_at_stage"] == "gatekeeper"

    async def test_mark_failed_raises_on_missing_content(self):
        """mark_failed raises ValueError if content does not exist."""
        storage = AsyncMock(spec=ContentStorageService)
        storage.update_pipeline_status.side_effect = ValueError("Content 999 not found")

        orchestrator = PipelineOrchestrator(storage)
        with pytest.raises(ValueError, match="Content.*not found"):
            await orchestrator.mark_failed(999, stage="gatekeeper", reason="err")
