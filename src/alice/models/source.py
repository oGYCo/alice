"""Source model."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SourceType(StrEnum):
    """Content source types."""

    rss = "rss"
    arxiv = "arxiv"


class Source(Base, TimestampMixin):
    """Content source (feed URL, arXiv endpoint, etc.)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="sourcetype"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
