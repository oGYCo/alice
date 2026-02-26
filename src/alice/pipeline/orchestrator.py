"""Pipeline orchestrator — state machine coordinating the 4-stage content pipeline.

Content lifecycle:
    fetched → gatekept → understood → scored → indexed
                                                     ↘ failed (at any stage)

State is stored ONLY in PostgreSQL content.pipeline_status.
Each stage dispatches the NEXT task individually — NO Celery chains.
"""

from __future__ import annotations

import json
import logging

from alice.models.content import PipelineStatus
from alice.services.storage import ContentStorageService

logger = logging.getLogger(__name__)


def _dispatch_next(stage: str, content_id: int) -> None:
    """Dispatch the next pipeline task for the given completed stage.

    Imports are lazy so that tests can patch individual task functions.
    Raises ValueError for unknown stages (caller must handle 'indexed' separately).
    """
    from alice.pipeline.tasks import (  # noqa: PLC0415
        task_run_indexing,
        task_run_scoring,
        task_run_understanding,
    )

    mapping = {
        "gatekept": task_run_understanding,
        "understood": task_run_scoring,
        "scored": task_run_indexing,
    }
    task = mapping.get(stage)
    if task is not None:
        task.delay(content_id)


class PipelineOrchestrator:
    """Coordinates the 4-stage content processing pipeline via PostgreSQL state."""

    def __init__(self, storage: ContentStorageService) -> None:
        self._storage = storage

    async def process_new_content(self, content_id: int) -> None:
        """Entry point — validates state=fetched, dispatches gatekeeper task.

        Args:
            content_id: Primary key of the content row.

        Raises:
            ValueError: If content not found or not in 'fetched' state.
        """
        from alice.pipeline.tasks import task_run_gatekeeper  # noqa: PLC0415

        content = await self._storage.get_by_id(content_id)
        if content is None:
            raise ValueError(f"Content {content_id} not found")

        if content.pipeline_status != PipelineStatus.fetched:
            raise ValueError(
                f"Expected status 'fetched' for content {content_id}, "
                f"got '{content.pipeline_status}'"
            )

        logger.info(
            "pipeline_start",
            extra={"content_id": content_id},
        )
        task_run_gatekeeper.delay(content_id)

    async def advance_pipeline(self, content_id: int, current_stage: str, result: dict) -> None:
        """Generic state advancer — determines next stage and dispatches next task.

        Called by each Celery task upon completion to advance the pipeline.

        Args:
            content_id: Primary key of the content row.
            current_stage: Stage that just completed (e.g. "gatekept", "understood").
            result: Stage result dict. For gatekeeper, must include "passed" bool.

        Raises:
            ValueError: If content not found or stage is unknown.
        """
        content = await self._storage.get_by_id(content_id)
        if content is None:
            raise ValueError(f"Content {content_id} not found")

        # Handle explicit failure signal
        if current_stage == "gatekeeper" and not result.get("passed", True):
            reason = result.get("reason", "gatekeeper rejected")
            await self.mark_failed(content_id, stage="gatekeeper", reason=reason)
            logger.info(
                "pipeline_gatekeeper_rejected",
                extra={"content_id": content_id, "reason": reason},
            )
            return

        # Map stage name → dispatch next task
        known_stages = {"gatekept", "understood", "scored", "indexed"}
        if current_stage not in known_stages:
            raise ValueError(f"Unknown stage: '{current_stage}'")

        if current_stage != "indexed":
            _dispatch_next(current_stage, content_id)
            logger.info(
                "pipeline_advance",
                extra={"content_id": content_id, "from_stage": current_stage},
            )
        else:
            # Terminal stage — pipeline complete
            logger.info(
                "pipeline_complete",
                extra={"content_id": content_id},
            )

    async def mark_failed(self, content_id: int, stage: str, reason: str) -> None:
        """Mark content as failed with structured error JSON.

        Args:
            content_id: Primary key of the content row.
            stage: Pipeline stage where the failure occurred.
            reason: Human-readable failure reason.

        Raises:
            ValueError: Propagated from storage if content not found.
        """
        error_json = json.dumps({"failure_reason": reason, "failed_at_stage": stage})
        await self._storage.update_pipeline_status(
            content_id, PipelineStatus.failed, error=error_json
        )
        logger.info(
            "pipeline_failed",
            extra={"content_id": content_id, "stage": stage, "reason": reason},
        )
