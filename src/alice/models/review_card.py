"""ReviewCard model for FSRS spaced repetition."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CardState(StrEnum):
    """FSRS card state machine states."""

    new = "new"
    learning = "learning"
    review = "review"
    relearning = "relearning"


class ReviewCard(Base, TimestampMixin):
    """Spaced repetition review card per FSRS v5."""

    __tablename__ = "review_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    concept_id: Mapped[str] = mapped_column(String(255), nullable=False)
    review_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # FSRS fields
    stability: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[CardState] = mapped_column(
        String(20),
        default=CardState.new,
        nullable=False,
    )
    reps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
