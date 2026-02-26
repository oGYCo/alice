"""UserMemory model for 3-tier memory system."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class MemoryLayer(StrEnum):
    """Memory tier layer."""

    working = "working"
    short_term = "short_term"
    long_term = "long_term"


class UserMemory(Base, TimestampMixin):
    """A single memory item in the 3-tier memory system."""

    __tablename__ = "user_memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    layer: Mapped[MemoryLayer] = mapped_column(String(20), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    last_touched: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
