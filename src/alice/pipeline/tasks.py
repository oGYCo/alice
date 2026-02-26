"""Pipeline Celery task definitions.

IMPORTANT: These are individual tasks — NO Celery chains.
Each task reads/writes pipeline_status to PostgreSQL via ContentStorageService.
On success: dispatches the next task manually via .delay().
On failure: sets status=failed with structured error JSON.

Tasks are sync (Celery workers are synchronous), but services are async.
We bridge this with asyncio.run() inside each task.
"""

from __future__ import annotations

import asyncio
import json
import logging

from alice.db import AsyncSessionLocal
from alice.llm.mock import MockLLMClient
from alice.models.content import PipelineStatus
from alice.services.gatekeeper import GatekeeperService
from alice.services.scoring import ScoringService
from alice.services.storage import ContentStorageService
from alice.services.understanding import UnderstandingService
from alice.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_storage(session) -> ContentStorageService:
    return ContentStorageService(session)


async def _fail_content(session, content_id: int, stage: str, reason: str) -> None:
    """Mark content as failed with structured error JSON in DB."""
    storage = ContentStorageService(session)
    error_json = json.dumps({"failure_reason": reason, "failed_at_stage": stage})
    await storage.update_pipeline_status(content_id, PipelineStatus.failed, error=error_json)


# ---------------------------------------------------------------------------
# Stage 1: Gatekeeper
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_gatekeeper",
    max_retries=3,
    retry_backoff=True,
)
def task_run_gatekeeper(self, content_id: int) -> dict:
    """Stage 1: Run gatekeeper filter.

    Reads:  content.pipeline_status == 'fetched'
    Writes: content.pipeline_status = 'gatekept' OR 'failed'
    Next:   task_run_understanding (if passed)
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            # Use MockLLMClient as fallback; real client injected via config in prod
            llm_client = MockLLMClient()
            gk = GatekeeperService(llm_client)

            text = content.extracted_text or content.raw_text or ""
            url = content.source_url or ""

            try:
                decision = await gk.evaluate(text, url)
            except Exception as exc:
                logger.error(
                    "gatekeeper_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                raise self.retry(exc=exc)

            if decision.passed:
                await storage.update_pipeline_status(content_id, PipelineStatus.gatekept)
                # Dispatch next stage — NO Celery chain
                task_run_understanding.delay(content_id)
                logger.info(
                    "gatekeeper_passed",
                    extra={"content_id": content_id, "method": decision.method},
                )
                return {
                    "content_id": content_id,
                    "stage": "gatekeeper",
                    "passed": True,
                }
            else:
                error_json = json.dumps(
                    {
                        "failure_reason": decision.reason,
                        "failed_at_stage": "gatekeeper",
                    }
                )
                await storage.update_pipeline_status(
                    content_id, PipelineStatus.failed, error=error_json
                )
                logger.info(
                    "gatekeeper_rejected",
                    extra={
                        "content_id": content_id,
                        "reason": decision.reason,
                    },
                )
                return {
                    "content_id": content_id,
                    "stage": "gatekeeper",
                    "passed": False,
                    "reason": decision.reason,
                }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 2: Understanding
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_understanding",
    max_retries=3,
    retry_backoff=True,
)
def task_run_understanding(self, content_id: int) -> dict:
    """Stage 2: Run content understanding (DeepSeek).

    Reads:  content.pipeline_status == 'gatekept'
    Writes: summary, key_points, domains, estimated_read_time + status='understood'
    Next:   task_run_scoring
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            llm_client = MockLLMClient()
            understanding_svc = UnderstandingService(llm_client)

            title = content.title or ""
            text = content.extracted_text or content.raw_text or ""
            language = content.language or "en"

            try:
                result = await understanding_svc.process(title, text, language)
            except Exception as exc:
                logger.error(
                    "understanding_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                error_json = json.dumps(
                    {
                        "failure_reason": str(exc),
                        "failed_at_stage": "understanding",
                    }
                )
                await storage.update_pipeline_status(
                    content_id, PipelineStatus.failed, error=error_json
                )
                raise self.retry(exc=exc)

            await storage.update_understanding(
                content_id,
                summary=result.summary,
                key_points=result.key_points,
                domains=result.domains,
                read_time=result.estimated_read_time,
            )
            # Dispatch next stage — NO Celery chain
            task_run_scoring.delay(content_id)
            logger.info(
                "understanding_complete",
                extra={"content_id": content_id, "domains": result.domains},
            )
            return {
                "content_id": content_id,
                "stage": "understanding",
                "domains": result.domains,
            }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 3: Scoring
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_scoring",
    max_retries=3,
    retry_backoff=True,
)
def task_run_scoring(self, content_id: int) -> dict:
    """Stage 3: Run quality scoring.

    Reads:  content.pipeline_status == 'understood', summary, key_points
    Writes: quality_score + status='scored'
    Next:   task_run_indexing
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            llm_client = MockLLMClient()
            scoring_svc = ScoringService(llm_client)

            title = content.title or ""
            summary = content.summary or ""
            key_points = content.key_points or []

            try:
                score_result = await scoring_svc.score(title, summary, key_points)
            except Exception as exc:
                logger.error(
                    "scoring_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                error_json = json.dumps(
                    {
                        "failure_reason": str(exc),
                        "failed_at_stage": "scoring",
                    }
                )
                await storage.update_pipeline_status(
                    content_id, PipelineStatus.failed, error=error_json
                )
                raise self.retry(exc=exc)

            await storage.update_score(
                content_id,
                score=score_result.score,
                reasoning=score_result.reasoning,
            )
            # Dispatch next stage — NO Celery chain
            task_run_indexing.delay(content_id)
            logger.info(
                "scoring_complete",
                extra={"content_id": content_id, "score": score_result.score},
            )
            return {
                "content_id": content_id,
                "stage": "scoring",
                "score": score_result.score,
            }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 4: Indexing
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_indexing",
    max_retries=3,
    retry_backoff=True,
)
def task_run_indexing(self, content_id: int) -> dict:
    """Stage 4: Mark content as indexed (ready for delivery).

    Reads:  content.pipeline_status == 'scored'
    Writes: content.pipeline_status = 'indexed'
    Next:   terminal — no further dispatch
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            try:
                await storage.update_pipeline_status(content_id, PipelineStatus.indexed)
            except Exception as exc:
                logger.error(
                    "indexing_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                raise self.retry(exc=exc)

            logger.info(
                "indexing_complete",
                extra={"content_id": content_id},
            )
            return {"content_id": content_id, "stage": "indexing"}

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Maintenance: retry failed content
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_retry_failed",
)
def task_retry_failed(self) -> dict:
    """Periodic task: re-queue content items stuck in 'failed' state.

    Triggered by Celery Beat every hour.
    Only retries items whose failure was transient (no permanent rejection flag).
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            failed_items = await storage.get_pending(PipelineStatus.failed, limit=50)
            requeued = 0
            for item in failed_items:
                # Skip permanently rejected content (gatekeeper rejections)
                error_data: dict = {}
                if item.pipeline_error:
                    try:
                        error_data = json.loads(item.pipeline_error)
                    except (json.JSONDecodeError, TypeError):
                        error_data = {}

                failed_stage = error_data.get("failed_at_stage", "")
                if failed_stage == "gatekeeper":
                    # Permanent rejection — do not retry
                    continue

                # Reset to fetched state so gatekeeper runs again
                await storage.update_pipeline_status(item.id, PipelineStatus.fetched)
                task_run_gatekeeper.delay(item.id)
                requeued += 1

            logger.info(
                "retry_failed_complete",
                extra={"requeued": requeued},
            )
            return {"requeued": requeued}

    return asyncio.run(_run())
