"""Feedback model."""

from enum import StrEnum

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class FeedbackType(StrEnum):
    """User feedback types."""

    valuable_learned = "valuable_learned"
    save_for_later = "save_for_later"
    not_valuable = "not_valuable"
    already_known = "already_known"


class Feedback(Base, TimestampMixin):
    """User feedback on content."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(Integer, ForeignKey("content.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    type: Mapped[FeedbackType] = mapped_column(
        Enum(FeedbackType, name="feedbacktype"), nullable=False
    )
