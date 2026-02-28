"""Content-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, computed_field, model_validator


class SubgraphNodeOut(BaseModel):
    """A concept node for the API subgraph response."""
    id: str
    name: str
    label: str = "Concept"
    mastery: float = 0.5


class SubgraphEdgeOut(BaseModel):
    """A concept edge for the API subgraph response."""
    from_: str = Field(alias="from")
    to: str
    relation: str

    model_config = {"populate_by_name": True}


class SubgraphOut(BaseModel):
    """Concept subgraph for a content item."""
    nodes: list[SubgraphNodeOut]
    edges: list[SubgraphEdgeOut]


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
    content_type: str | None = None  # "knowledge" | "thought" | "news"


class ContentResponseSchema(BaseModel):
    """API response for content item."""

    id: int
    source: str
    source_url: str
    title: str | None = None
    content_type: str | None = None
    pipeline_status: str
    quality_score: float | None = None
    summary: str | None = None
    key_points: list[str] | None = None
    domains: list[str] | None = None
    estimated_read_time: int | None = None
    metadata_: dict | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _extract_content_type(self) -> "ContentResponseSchema":
        """Populate content_type from metadata_ if not set directly."""
        if self.content_type is None and isinstance(self.metadata_, dict):
            self.content_type = self.metadata_.get("content_type")  # type: ignore[assignment]
        return self


class ContentDetailSchema(ContentResponseSchema):
    """Enriched schema for GET /content/{id} — includes full article text and subgraph."""

    # Pydantic reads extracted_text directly from the ORM object via from_attributes.
    extracted_text: str | None = None
    raw_text: str | None = Field(default=None, exclude=True)
    subgraph: SubgraphOut | None = None

    @computed_field  # type: ignore[misc]
    @property
    def full_content(self) -> str | None:
        """Prefer extracted full text, fallback to raw text when extraction fails."""
        return self.extracted_text or self.raw_text
