"""Content pipeline state machine schemas."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class PipelineStatus(StrEnum):
    """Stages in the content processing pipeline."""

    fetched = "fetched"
    gatekept = "gatekept"
    understood = "understood"
    scored = "scored"
    indexed = "indexed"
    failed = "failed"


class PipelineTaskSchema(BaseModel):
    """Represents a pipeline task for a content item."""

    content_id: int
    status: PipelineStatus
    stage: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
