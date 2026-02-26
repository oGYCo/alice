"""Source configuration and fetching result schemas."""


from pydantic import BaseModel, Field


class SourceConfigSchema(BaseModel):
    """Configuration for a content source."""

    name: str
    url: str
    type: str = Field(..., pattern="^(rss|arxiv)$")
    config: dict = Field(default_factory=dict)
    enabled: bool = True
    fetch_interval_minutes: int = Field(default=30, ge=5, le=1440)


class FetchResultSchema(BaseModel):
    """Result of fetching from a source."""

    source_url: str
    items_fetched: int
    items_new: int
    items_skipped: int
    errors: list[str] = Field(default_factory=list)
