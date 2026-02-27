"""FastAPI router for search and suggest endpoints."""

from __future__ import annotations

from typing import Any

import meilisearch.errors
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from alice.config import settings
from alice.graph.client import GraphClient
from alice.llm.factory import create_llm_client
from alice.services.graphrag_query import GraphRAGQueryEngine, QueryMode, RankedResult
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


class HybridHitSchema(BaseModel):
    content_id: str
    score: float
    source: str
    graph_score: float = 0.0
    text_score: float = 0.0
    semantic_score: float = 0.0


class HybridSearchResponseSchema(BaseModel):
    results: list[HybridHitSchema]
    total: int
    query: str
    mode: str


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
        result = svc.search(q, filters=filters, limit=limit, offset=offset)
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

    try:
        result = svc.search(q, limit=limit)
    except meilisearch.errors.MeilisearchApiError:
        raise HTTPException(status_code=503, detail="Search service unavailable")
    titles = [h["title"] for h in result.get("hits", []) if h.get("title")]
    return SuggestResponseSchema(suggestions=titles, query=q)


@router.post("/hybrid", response_model=HybridSearchResponseSchema)
async def hybrid_search(
    q: str = Query(..., min_length=1, description="Natural-language query string"),
    user_id: int = Query(default=1, ge=1, description="User ID for personalisation"),
    mode: str = Query(default="hybrid", description="Search mode: hybrid, graph_only, text_only"),
    limit: int = Query(default=10, ge=1, le=50),
    svc: SearchService = Depends(_get_search_service),
) -> Any:
    """Hybrid search combining Neo4j graph traversal, Meilisearch full-text, and semantic matching.

    Returns results ranked by a weighted fusion of all retrieval backends.
    Graceful degradation: if Neo4j is unavailable, falls back to text-only search.
    """
    # Validate mode
    try:
        query_mode = QueryMode(mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{mode}'. Must be one of: hybrid, graph_only, text_only",
        )

    graph_client: GraphClient | None = None
    try:
        user, password = settings.NEO4J_AUTH.split("/", 1)
        graph_client = GraphClient(settings.NEO4J_URI, (user, password))
        await graph_client.connect()

        llm_client = create_llm_client("deepseek")

        engine = GraphRAGQueryEngine(
            graph_client=graph_client,
            search_service=svc,
            llm_client=llm_client,
        )

        results: list[RankedResult] = await engine.query(
            text=q,
            user_id=user_id,
            mode=query_mode,
            limit=limit,
        )

        return HybridSearchResponseSchema(
            results=[
                HybridHitSchema(
                    content_id=r.content_id,
                    score=round(r.score, 4),
                    source=r.source,
                    graph_score=round(r.graph_score, 4),
                    text_score=round(r.text_score, 4),
                    semantic_score=round(r.semantic_score, 4),
                )
                for r in results
            ],
            total=len(results),
            query=q,
            mode=query_mode.value,
        )
    except Exception as exc:
        # If graph is unavailable and mode requires it, report error
        if query_mode == QueryMode.GRAPH_ONLY:
            raise HTTPException(
                status_code=503,
                detail=f"Graph search unavailable: {exc}",
            )
        # Fallback to text-only for hybrid mode
        try:
            text_result = svc.search(q, limit=limit)
            hits = text_result.get("hits", [])
            return HybridSearchResponseSchema(
                results=[
                    HybridHitSchema(
                        content_id=str(h["id"]),
                        score=round(1.0 - (i / max(len(hits), 1)), 4),
                        source="text",
                        text_score=round(1.0 - (i / max(len(hits), 1)), 4),
                    )
                    for i, h in enumerate(hits)
                ],
                total=len(hits),
                query=q,
                mode="text_only_fallback",
            )
        except meilisearch.errors.MeilisearchApiError:
            raise HTTPException(status_code=503, detail="All search backends unavailable")
    finally:
        if graph_client:
            await graph_client.close()
