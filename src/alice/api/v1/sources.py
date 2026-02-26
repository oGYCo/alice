"""Sources API router — POST /sources, GET /sources."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.schemas.source import SourceConfigSchema
from alice.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"])


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
    return source


@router.get("", response_model=list[SourceResponseSchema])
async def list_sources(
    svc: SourceService = Depends(_get_source_service),
) -> Any:
    """List all active content sources."""
    sources = await svc.list_active()
    return sources
