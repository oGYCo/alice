"""Content API router — GET /content, GET /content/{id}."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.models.content import PipelineStatus
from alice.schemas.content import ContentResponseSchema
from alice.services.storage import ContentStorageService

router = APIRouter(prefix="/content", tags=["content"])


def _get_storage(session: Annotated[AsyncSession, Depends(get_db)]) -> ContentStorageService:
    return ContentStorageService(session)


@router.get("", response_model=list[ContentResponseSchema])
async def list_content(
    status: Annotated[PipelineStatus | None, Query(description="Filter by pipeline status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    svc: ContentStorageService = Depends(_get_storage),
) -> Any:
    """List content items, optionally filtered by pipeline status."""
    if status is not None:
        items = await svc.get_pending(stage=status, limit=limit)
    else:
        # Return recent fetched items when no filter given
        items = await svc.get_pending(stage=PipelineStatus.fetched, limit=limit)
    return items


@router.get("/{content_id}", response_model=ContentResponseSchema)
async def get_content(
    content_id: int,
    svc: ContentStorageService = Depends(_get_storage),
) -> Any:
    """Get a single content item by ID."""
    content = await svc.get_by_id(content_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")
    return content
