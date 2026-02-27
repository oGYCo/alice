"""Content API router — GET /content, GET /content/{id}."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from alice.config import settings
from alice.db import get_db
from alice.models.content import PipelineStatus
from alice.schemas.content import ContentDetailSchema, ContentResponseSchema, SubgraphOut
from alice.services.search import SearchService
from alice.services.storage import ContentStorageService

router = APIRouter(prefix="/content", tags=["content"])


def _get_storage(session: Annotated[AsyncSession, Depends(get_db)]) -> ContentStorageService:
    return ContentStorageService(session)


def _get_search() -> SearchService:
    return SearchService(url=settings.MEILISEARCH_URL, api_key=settings.MEILISEARCH_API_KEY)


@router.get("", response_model=list[ContentResponseSchema])
async def list_content(
    status: Annotated[PipelineStatus | None, Query(description="Filter by pipeline status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[str, Query(pattern="^(relevance|newest|oldest)$")] = "newest",
    svc: ContentStorageService = Depends(_get_storage),
) -> Any:
    """List content items, optionally filtered by pipeline status."""
    try:
        return await svc.list_content(
            status=status,
            limit=limit,
            offset=offset,
            sort=sort,
        )
    except OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Check DATABASE_URL and database service status.",
        )
    except ProgrammingError:
        raise HTTPException(
            status_code=500,
            detail="Database schema mismatch. Run `uv run alembic upgrade head`.",
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database query failed while listing content.",
        )


@router.get("/{content_id}", response_model=ContentDetailSchema)
async def get_content(
    content_id: int,
    svc: ContentStorageService = Depends(_get_storage),
) -> Any:
    """Get a single content item by ID."""
    try:
        content = await svc.get_by_id(content_id)
    except OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Check DATABASE_URL and database service status.",
        )
    except ProgrammingError:
        raise HTTPException(
            status_code=500,
            detail="Database schema mismatch. Run `uv run alembic upgrade head`.",
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database query failed while fetching content.",
        )
    if content is None:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")

    # Build base schema from ORM object
    detail = ContentDetailSchema.model_validate(content)

    # Query Neo4j for concept subgraph (best-effort — skipped if Neo4j is down)
    try:
        from alice.config import settings
        from alice.graph.client import GraphClient
        from alice.graph.repository import GraphRepository
        from alice.schemas.content import SubgraphEdgeOut, SubgraphNodeOut

        user, password = settings.NEO4J_AUTH.split("/", 1)
        async with GraphClient(settings.NEO4J_URI, (user, password)) as graph_client:
            graph_repo = GraphRepository(graph_client)
            raw = await graph_repo.get_content_subgraph(content_id)
            if raw["nodes"]:
                nodes = [SubgraphNodeOut(**n) for n in raw["nodes"]]
                edges = [
                    SubgraphEdgeOut.model_validate({"from": e["from"], "to": e["to"], "relation": e["relation"]})
                    for e in raw["edges"]
                ]
                detail = detail.model_copy(update={"subgraph": SubgraphOut(nodes=nodes, edges=edges)})
    except Exception:
        pass  # Neo4j unavailable or no data — subgraph stays None

    return detail


@router.post("/admin/extract-graphs", status_code=202)
async def trigger_graph_extraction(
    svc: ContentStorageService = Depends(_get_storage),
) -> dict[str, int]:
    """Admin: trigger graph extraction for all indexed content lacking Neo4j data.

    Dispatches task_run_graph_extraction for each indexed item.
    Returns count of tasks dispatched.
    """
    from alice.pipeline.tasks import task_run_graph_extraction

    items = await svc.get_pending(PipelineStatus.indexed, limit=500)
    for item in items:
        task_run_graph_extraction.delay(item.id)
    return {"dispatched": len(items)}


@router.delete("/{content_id}", status_code=204)
async def delete_content(
    content_id: int,
    svc: ContentStorageService = Depends(_get_storage),
    search: SearchService = Depends(_get_search),
) -> Response:
    """Delete a single content item by ID (DB + search index)."""
    try:
        deleted = await svc.delete_by_id(content_id)
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while deleting content.")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")
    # Best-effort: remove from Meilisearch (won't fail the request if Meili is down)
    search.delete_document(content_id)
    return Response(status_code=204)


class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.delete("", status_code=200)
async def delete_content_batch(
    body: BatchDeleteRequest,
    svc: ContentStorageService = Depends(_get_storage),
    search: SearchService = Depends(_get_search),
) -> dict[str, int]:
    """Delete multiple content items by IDs (DB + search index). Returns count of deleted rows."""
    try:
        count = await svc.delete_batch(body.ids)
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while deleting content.")
    # Best-effort: remove from Meilisearch
    search.delete_documents(body.ids)
    return {"deleted": count}
