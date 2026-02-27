"""Legacy Celery task stubs kept for backward compatibility.

Active pipeline execution lives in ``alice.pipeline.tasks``. These stubs are
retained so older task names continue to resolve if any existing producers or
Beat schedules still reference ``alice.worker.tasks.*``.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.connectors.arxiv import ArxivConnector
from alice.connectors.rss import RSSConnector
from alice.db import AsyncSessionLocal
from alice.models.content import Content
from alice.models.source import Source, SourceType
from alice.schemas.source import SourceConfigSchema
from alice.services.source_service import SourceService
from alice.services.storage import ContentStorageService, normalize_url
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
    # Legacy stub. Real implementation: alice.pipeline.tasks.task_run_gatekeeper
    return {"content_id": content_id, "stage": "gatekeeper", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_understanding")
def task_run_understanding(self, content_id: int) -> dict:
    """
    Stage 2: Run content understanding (DeepSeek).

    Reads: content.pipeline_status == "gatekept"
    Writes: content.summary, key_points, domains + pipeline_status = "understood"
    """
    logger.info(f"Running understanding for content_id={content_id}")
    # Legacy stub. Real implementation: alice.pipeline.tasks.task_run_understanding
    return {"content_id": content_id, "stage": "understanding", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_scoring")
def task_run_scoring(self, content_id: int) -> dict:
    """
    Stage 3: Run quality scoring.

    Reads: content.pipeline_status == "understood"
    Writes: content.quality_score + pipeline_status = "scored"
    """
    logger.info(f"Running scoring for content_id={content_id}")
    # Legacy stub. Real implementation: alice.pipeline.tasks.task_run_scoring
    return {"content_id": content_id, "stage": "scoring", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_indexing")
def task_run_indexing(self, content_id: int) -> dict:
    """
    Stage 4: Index content for delivery.

    Reads: content.pipeline_status == "scored"
    Writes: content.pipeline_status = "indexed"
    """
    logger.info(f"Running indexing for content_id={content_id}")
    # Legacy stub. Real implementation: alice.pipeline.tasks.task_run_indexing
    return {"content_id": content_id, "stage": "indexing", "status": "stub"}


@celery_app.task(bind=True, name="alice.worker.tasks.task_fetch_all_sources")
def task_fetch_all_sources(self, source_id: int | None = None) -> dict:
    """
    Scheduler task: Fetch content from all active sources.

    Triggered by: Celery Beat (every 30 minutes)
    """

    try:
        return asyncio.run(fetch_all_sources_once(source_id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("fetch_all_sources_unhandled_error")
        return {
            "status": "error",
            "requested_source_id": source_id,
            "sources_triggered": 0,
            "sources_fetched": 0,
            "items_fetched": 0,
            "items_new": 0,
            "items_existing": 0,
            "dispatched": 0,
            "errors": [{"reason": str(exc)}],
        }


async def fetch_all_sources_once(
    source_id: int | None = None,
    session: AsyncSession | None = None,
) -> dict:
    """Fetch configured sources once and store raw content.

    This async helper is used both by Celery workers and by API-triggered manual
    fetches. Keeping logic in one place avoids event-loop mismatches in API.
    """
    connector_map = {
        SourceType.rss.value: RSSConnector,
        SourceType.arxiv.value: ArxivConnector,
    }
    errors: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "status": "ok",
        "requested_source_id": source_id,
        "sources_triggered": 0,
        "sources_fetched": 0,
        "items_fetched": 0,
        "items_new": 0,
        "items_existing": 0,
        "dispatched": 0,
        "errors": errors,
    }

    from alice.pipeline.tasks import task_run_gatekeeper

    async def _run(current_session: AsyncSession) -> dict:
        source_service = SourceService(current_session)
        storage = ContentStorageService(current_session)

        query = select(Source).where(Source.is_active == True)  # noqa: E712
        if source_id is not None:
            query = query.where(Source.id == source_id)
        result = await current_session.execute(query.order_by(Source.id.asc()))
        sources = result.scalars().all()
        summary["sources_triggered"] = len(sources)

        for source in sources:
            source_type = source.type.value if isinstance(source.type, SourceType) else str(source.type)
            connector_cls = connector_map.get(source_type)
            if connector_cls is None:
                errors.append(
                    {
                        "source_id": source.id,
                        "reason": f"unsupported source type: {source_type}",
                    }
                )
                continue

            config = SourceConfigSchema(
                name=source.name,
                url=source.url,
                type=source_type,
                config=source.config or {},
                enabled=source.is_active,
                fetch_interval_minutes=source.fetch_interval_minutes,
            )

            try:
                connector = connector_cls()
                raw_items = await connector.fetch(config)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "source_fetch_failed",
                    extra={"source_id": source.id, "source_type": source_type},
                )
                errors.append({"source_id": source.id, "reason": str(exc)})
                continue

            summary["sources_fetched"] = int(summary["sources_fetched"]) + 1
            summary["items_fetched"] = int(summary["items_fetched"]) + len(raw_items)

            for raw in raw_items:
                normalized_source_url = normalize_url(raw.source_url)
                exists_result = await current_session.execute(
                    select(Content.id).where(Content.source_url == normalized_source_url)
                )
                existing_id = exists_result.scalar_one_or_none()
                content = await storage.store_raw(raw)
                if existing_id is None:
                    summary["items_new"] = int(summary["items_new"]) + 1
                    try:
                        task_run_gatekeeper.delay(content.id)
                        summary["dispatched"] = int(summary["dispatched"]) + 1
                    except Exception as exc:  # noqa: BLE001
                        errors.append(
                            {
                                "content_id": content.id,
                                "reason": f"dispatch_failed: {exc}",
                            }
                        )
                else:
                    summary["items_existing"] = int(summary["items_existing"]) + 1

            await source_service.mark_fetched(source.id)

        logger.info("fetch_all_sources_complete", extra=summary)
        return summary

    if session is not None:
        return await _run(session)

    async with AsyncSessionLocal() as managed_session:
        return await _run(managed_session)


@celery_app.task(bind=True, name="alice.worker.tasks.task_push_batch")
def task_push_batch(self, user_id: int) -> dict:
    """
    Push a batch of content to a user via Telegram.

    Triggered by: Celery Beat or manual trigger
    """
    logger.info(f"Pushing content batch to user_id={user_id}")
    # Legacy stub. Real implementation: alice.pipeline.tasks.task_push_batch
    return {"user_id": user_id, "status": "stub", "items_pushed": 0}
