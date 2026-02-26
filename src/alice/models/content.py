"""Content model."""
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class PipelineStatus(StrEnum):
    """Pipeline processing status."""

    fetched = "fetched"
    gatekept = "gatekept"
    understood = "understood"
    scored = "scored"
    indexed = "indexed"
    failed = "failed"


class Content(Base, TimestampMixin):
    """Content from various sources."""

    __tablename__ = "content"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    metadata_: Mapped[dict] = mapped_column(JSON, default=dict, name="metadata")
    pipeline_status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipelinestatus"),
        default=PipelineStatus.fetched,
        nullable=False,
    )
    pipeline_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    domains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    estimated_read_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
