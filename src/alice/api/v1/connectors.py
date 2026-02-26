from __future__ import annotations

import importlib

from fastapi import APIRouter  # type: ignore[import-not-found]
from pydantic import BaseModel, Field  # type: ignore[import-not-found]

_rss_module = importlib.import_module("alice.connectors.rss")
_content_module = importlib.import_module("alice.schemas.content")
_source_module = importlib.import_module("alice.schemas.source")

RSSConnector = _rss_module.RSSConnector
RawContentSchema = _content_module.RawContentSchema
SourceConfigSchema = _source_module.SourceConfigSchema

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
