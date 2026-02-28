"""Legacy Celery task wrappers kept for backward compatibility.

Active pipeline execution lives in ``alice.pipeline.tasks``. These wrappers
are retained so older task names continue to resolve if any existing producers
or Beat schedules still reference ``alice.worker.tasks.*``.

Each wrapper forwards to the real pipeline task and logs a deprecation warning.
"""

from __future__ import annotations

import asyncio
import logging
import warnings

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

_DEPRECATION_MSG = (
    "Task name 'alice.worker.tasks.{name}' is deprecated. "
    "Use 'alice.pipeline.tasks.{name}' instead."
)


def _deprecation_warn(name: str) -> None:
    """Log and emit a deprecation warning for legacy task names."""
    msg = _DEPRECATION_MSG.format(name=name)
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning, stacklevel=3)


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_gatekeeper")
def task_run_gatekeeper(self, content_id: int) -> dict:
    """Legacy wrapper — forwards to alice.pipeline.tasks.task_run_gatekeeper."""
    _deprecation_warn("task_run_gatekeeper")
    from alice.pipeline.tasks import task_run_gatekeeper as real_task  # noqa: PLC0415

    return real_task(content_id)


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_understanding")
def task_run_understanding(self, content_id: int) -> dict:
    """Legacy wrapper — forwards to alice.pipeline.tasks.task_run_understanding."""
    _deprecation_warn("task_run_understanding")
    from alice.pipeline.tasks import task_run_understanding as real_task  # noqa: PLC0415

    return real_task(content_id)


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_scoring")
def task_run_scoring(self, content_id: int) -> dict:
    """Legacy wrapper — forwards to alice.pipeline.tasks.task_run_scoring."""
    _deprecation_warn("task_run_scoring")
    from alice.pipeline.tasks import task_run_scoring as real_task  # noqa: PLC0415

    return real_task(content_id)


@celery_app.task(bind=True, name="alice.worker.tasks.task_run_indexing")
def task_run_indexing(self, content_id: int) -> dict:
    """Legacy wrapper — forwards to alice.pipeline.tasks.task_run_indexing."""
    _deprecation_warn("task_run_indexing")
    from alice.pipeline.tasks import task_run_indexing as real_task  # noqa: PLC0415

    return real_task(content_id)


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
    """Legacy wrapper — forwards to alice.pipeline.tasks.task_push_batch.

    Note: the real task requires chat_id; this wrapper cannot supply it.
    A deprecation warning is emitted so callers migrate to the pipeline task.
    """
    _deprecation_warn("task_push_batch")
    logger.error(
        "task_push_batch called via legacy name without chat_id; "
        "migrate to alice.pipeline.tasks.task_push_batch"
    )
    return {
        "user_id": user_id,
        "status": "error",
        "error": "Legacy task_push_batch requires migration: missing chat_id parameter",
    }
