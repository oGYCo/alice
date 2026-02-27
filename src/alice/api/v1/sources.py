"""Sources API router — POST /sources, GET /sources, PUT /sources/{id}, DELETE /sources/{id}."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.schemas.source import SourceConfigSchema, SourceUpdateSchema
from alice.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)


class SourceResponseSchema(BaseModel):
    """API response for a source."""

    id: int
    type: str
    name: str
    url: str
    config: dict[str, Any]
    is_active: bool
    fetch_interval_minutes: int

    model_config = {"from_attributes": True}


def _get_source_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SourceService:
    return SourceService(session)


@router.post("", response_model=SourceResponseSchema, status_code=201)
async def create_source(
    config: SourceConfigSchema,
    svc: SourceService = Depends(_get_source_service),
) -> Any:
    """Create a new content source."""
    source = await svc.create(config)
    # Best-effort bootstrap fetch so newly added sources can populate feed quickly.
    try:
        from alice.worker.tasks import task_fetch_all_sources

        task_fetch_all_sources.delay(source.id)
    except Exception:  # noqa: BLE001
        # Source creation should not fail if broker is unavailable.
        logger.warning("source_bootstrap_fetch_dispatch_failed", extra={"source_id": source.id})
    return source


@router.get("", response_model=list[SourceResponseSchema])
async def list_sources(
    svc: SourceService = Depends(_get_source_service),
) -> Any:
    """List all active content sources."""
    sources = await svc.list_active()
    return sources


@router.put("/{source_id}", response_model=SourceResponseSchema)
async def update_source(
    source_id: int,
    update: SourceUpdateSchema,
    svc: SourceService = Depends(_get_source_service),
) -> Any:
    """Update an existing source (partial update)."""
    try:
        source = await svc.update_source(source_id, **update.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    svc: SourceService = Depends(_get_source_service),
) -> Response:
    """Delete a source by id. Returns 204 No Content."""
    try:
        await svc.delete_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
