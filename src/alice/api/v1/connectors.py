from __future__ import annotations

from fastapi import APIRouter  # type: ignore[import-not-found]
from pydantic import BaseModel, Field  # type: ignore[import-not-found]

from alice.connectors.arxiv import ArxivConnector
from alice.connectors.rss import RSSConnector
from alice.schemas.content import RawContentSchema
from alice.schemas.source import SourceConfigSchema

router = APIRouter(prefix="/connectors", tags=["connectors"])


class RSSFetchRequest(BaseModel):
    feed_url: str
    limit: int = Field(default=10, ge=1, le=200)


@router.post("/rss/fetch", response_model=list[RawContentSchema])
async def fetch_rss(request: RSSFetchRequest) -> list[RawContentSchema]:
    config = SourceConfigSchema(
        name="rss",
        url=request.feed_url,
        type="rss",
        config={"limit": request.limit},
    )
    connector = RSSConnector()
    return await connector.fetch(config)


class ArxivFetchRequest(BaseModel):
    query: str = Field(default="cat:cs.AI")
    max_results: int = Field(default=10, ge=1, le=100)


@router.post("/arxiv/fetch", response_model=list[RawContentSchema])
async def fetch_arxiv(request: ArxivFetchRequest) -> list[RawContentSchema]:
    config = SourceConfigSchema(
        name="arxiv",
        url=request.query,
        type="arxiv",
        config={"max_results": request.max_results},
    )
    connector = ArxivConnector()
    return await connector.fetch(config)
