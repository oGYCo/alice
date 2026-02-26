"""Content-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class RawContentSchema(BaseModel):
    """Raw content as fetched from source."""

    source: str  # "rss", "arxiv", etc.
    source_url: str
    source_id: str | None = None
    title: str | None = None
    raw_text: str | None = None
    extracted_text: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    language: str | None = None
    metadata: dict = Field(default_factory=dict)
    extraction_failed: bool = False


class ContentUnderstandingSchema(BaseModel):
    """Phase 0: 4 fields only (not full 14-field version)."""

    summary: str
    key_points: list[str]
    domains: list[str]
    estimated_read_time: int = Field(ge=1)  # minutes, must be >= 1


class ContentResponseSchema(BaseModel):
    """API response for content item."""

    id: int
    source: str
    source_url: str
    title: str | None = None
    pipeline_status: str
    quality_score: float | None = None
    summary: str | None = None
    key_points: list[str] | None = None
    domains: list[str] | None = None
    estimated_read_time: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
