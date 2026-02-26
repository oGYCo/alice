"""Celery task definitions for the Alice pipeline.

IMPORTANT: These are individual tasks dispatched by the PipelineOrchestrator.
Do NOT use Celery chains — each task reads/writes pipeline_status to PostgreSQL.
"""

import logging

from alice.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_gatekeeper")
def task_run_gatekeeper(self, content_id: int) -> dict:
    """
    Stage 1: Run gatekeeper filter on content.

    Reads: content.pipeline_status == "fetched"
    Writes: content.pipeline_status = "gatekept" OR "failed"
    """
    logger.info(f"Running gatekeeper for content_id={content_id}")
    # TODO: Implemented in Task 9 (GatekeeperService)
    # This stub validates the task infrastructure works
    return {"content_id": content_id, "stage": "gatekeeper", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_understanding")
def task_run_understanding(self, content_id: int) -> dict:
    """
    Stage 2: Run content understanding (DeepSeek).

    Reads: content.pipeline_status == "gatekept"
    Writes: content.summary, key_points, domains + pipeline_status = "understood"
    """
    logger.info(f"Running understanding for content_id={content_id}")
    # TODO: Implemented in Task 10 (UnderstandingService)
    return {"content_id": content_id, "stage": "understanding", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_scoring")
def task_run_scoring(self, content_id: int) -> dict:
    """
    Stage 3: Run quality scoring.

    Reads: content.pipeline_status == "understood"
    Writes: content.quality_score + pipeline_status = "scored"
    """
    logger.info(f"Running scoring for content_id={content_id}")
    # TODO: Implemented in Task 11 (ScoringService)
    return {"content_id": content_id, "stage": "scoring", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_indexing")
def task_run_indexing(self, content_id: int) -> dict:
    """
    Stage 4: Index content for delivery.

    Reads: content.pipeline_status == "scored"
    Writes: content.pipeline_status = "indexed"
    """
    logger.info(f"Running indexing for content_id={content_id}")
    # TODO: Implemented in Task 13 (PipelineOrchestrator)
    return {"content_id": content_id, "stage": "indexing", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_fetch_all_sources")
def task_fetch_all_sources(self) -> dict:
    """
    Scheduler task: Fetch content from all active sources.

    Triggered by: Celery Beat (every 30 minutes)
    """
    logger.info("Fetching content from all active sources")
    # TODO: Implemented in Task 15 (SchedulerService)
    return {"status": "stub", "sources_triggered": 0}


@celery_app.task(bind=True, name="alice.worker.tasks.task_push_batch")
def task_push_batch(self, user_id: int) -> dict:
    """
    Push a batch of content to a user via Telegram.

    Triggered by: Celery Beat or manual trigger
    """
    logger.info(f"Pushing content batch to user_id={user_id}")
    # TODO: Implemented in Task 16 (PushService)
    return {"user_id": user_id, "status": "stub", "items_pushed": 0}
