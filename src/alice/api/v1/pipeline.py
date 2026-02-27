"""Pipeline control API — process, status, retry endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.models.content import Content, PipelineStatus
from alice.pipeline.tasks import task_run_gatekeeper
from alice.services.storage import ContentStorageService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ProcessRequest(BaseModel):
    content_id: int


class PipelineStatusResponse(BaseModel):
    queued: int
    processing: int
    completed: int
    failed: int


class FetchTriggerRequest(BaseModel):
    source_id: int | None = None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_storage(session: Annotated[AsyncSession, Depends(get_db)]) -> ContentStorageService:
    return ContentStorageService(session)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/process", status_code=202)
async def process_content(
    body: ProcessRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Trigger pipeline processing for a content item.

    The content must already exist with pipeline_status='fetched'.
    Returns 202 Accepted immediately; processing is async.
    """
    storage = ContentStorageService(session)
    content = await storage.get_by_id(body.content_id)
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=f"Content {body.content_id} not found",
        )
    if content.pipeline_status != PipelineStatus.fetched:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Content {body.content_id} is not in 'fetched' state "
                f"(current: {content.pipeline_status})"
            ),
        )

    task_run_gatekeeper.delay(body.content_id)
    return {"content_id": body.content_id, "status": "queued"}


@router.get("/status", response_model=PipelineStatusResponse)
async def pipeline_status(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Return aggregate pipeline status counts."""
    # queued = fetched (not yet dispatched)
    # processing = gatekept + understood + scored (in-flight)
    # completed = indexed
    # failed = failed

    async def _count(statuses: list[PipelineStatus]) -> int:
        result = await session.execute(
            select(func.count()).where(Content.pipeline_status.in_(statuses))
        )
        return result.scalar_one()

    queued = await _count([PipelineStatus.fetched])
    processing = await _count(
        [PipelineStatus.gatekept, PipelineStatus.understood, PipelineStatus.scored]
    )
    completed = await _count([PipelineStatus.indexed])
    failed = await _count([PipelineStatus.failed])

    return PipelineStatusResponse(
        queued=queued,
        processing=processing,
        completed=completed,
        failed=failed,
    )


@router.post("/retry/{content_id}", status_code=202)
async def retry_content(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Retry processing for a failed content item.

    Resets the status to 'fetched' and re-dispatches gatekeeper.
    """
    storage = ContentStorageService(session)
    content = await storage.get_by_id(content_id)
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=f"Content {content_id} not found",
        )
    if content.pipeline_status != PipelineStatus.failed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Content {content_id} is not in 'failed' state "
                f"(current: {content.pipeline_status})"
            ),
        )

    await storage.update_pipeline_status(content_id, PipelineStatus.fetched)
    task_run_gatekeeper.delay(content_id)
    return {"content_id": content_id, "status": "queued"}


@router.post("/fetch/trigger")
async def trigger_fetch(
    body: FetchTriggerRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Fetch sources immediately in-process.

    This endpoint is useful in local development when Celery worker/beat is not
    running. It executes the fetch task synchronously in the API process.
    """
    from alice.worker.tasks import fetch_all_sources_once

    return await fetch_all_sources_once(body.source_id, session=session)


# ---------------------------------------------------------------------------
# Push endpoints
# ---------------------------------------------------------------------------


class PushTriggerRequest(BaseModel):
    user_id: int
    chat_id: int
    limit: int = 5


@router.post("/push/trigger", status_code=202)
async def trigger_push(
    body: PushTriggerRequest,
) -> Any:
    """Trigger a push batch delivery for a user.

    Dispatches task_push_batch as a background Celery task.
    Returns 202 Accepted immediately.
    """
    from alice.pipeline.tasks import task_push_batch

    task_push_batch.delay(body.user_id, body.chat_id, body.limit)
    return {"user_id": body.user_id, "chat_id": body.chat_id, "status": "queued"}


@router.get("/push/preview")
async def preview_push_card(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Return the formatted push card text for a content item.

    Useful for testing card rendering without delivering to Telegram.
    """
    from alice.services.push import PushService

    storage = ContentStorageService(session)
    content = await storage.get_by_id(content_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")

    svc = PushService()
    card_text = svc.format_push_card(content)
    return {"content_id": content_id, "card_text": card_text}
