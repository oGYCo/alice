"""FastAPI router for search and suggest endpoints."""

from __future__ import annotations

from typing import Any

import meilisearch.errors
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alice.config import settings
from alice.services.search import SearchService


class SearchResponseSchema(BaseModel):
    hits: list[dict]
    total: int
    query: str
    offset: int
    limit: int
    facets: dict


class SuggestResponseSchema(BaseModel):
    suggestions: list[str]
    query: str


def _get_search_service() -> SearchService:
    return SearchService(
        url=settings.MEILISEARCH_URL,
        api_key=settings.MEILISEARCH_API_KEY,
    )


router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponseSchema)
async def search_content(
    q: str,
    type: str | None = None,
    min_score: float | None = None,
    limit: int = 10,
    offset: int = 0,
    svc: SearchService = Depends(_get_search_service),
) -> Any:
    """Full-text search over indexed content items."""
    if q.strip() == "":
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    filters: str | None = None
    if type is not None and min_score is not None:
        filters = f"content_type = '{type}' AND quality_score >= {min_score}"
    elif type is not None:
        filters = f"content_type = '{type}'"
    elif min_score is not None:
        filters = f"quality_score >= {min_score}"

    try:
        result = svc.search(q, filters=filters, limit=limit)
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=503, detail="Search service unavailable")

    return SearchResponseSchema(
        hits=result.get("hits", []),
        total=result.get("estimatedTotalHits", 0),
        query=q,
        offset=offset,
        limit=limit,
        facets=result.get("facetDistribution") or {},
    )


@router.get("/suggest", response_model=SuggestResponseSchema)
async def suggest_content(
    q: str,
    limit: int = 5,
    svc: SearchService = Depends(_get_search_service),
) -> Any:
    """Return title suggestions based on a partial query."""
    if q.strip() == "":
        return SuggestResponseSchema(suggestions=[], query="")

    result = svc.search(q, limit=limit)
    titles = [h["title"] for h in result.get("hits", []) if h.get("title")]
    return SuggestResponseSchema(suggestions=titles, query=q)
