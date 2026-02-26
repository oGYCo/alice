"""User feedback schemas."""

from enum import StrEnum

from pydantic import BaseModel


class FeedbackType(StrEnum):
    """Types of user feedback."""

    valuable_learned = "valuable_learned"
    save_for_later = "save_for_later"
    not_valuable = "not_valuable"
    already_known = "already_known"


class FeedbackCreateSchema(BaseModel):
    """Schema for creating user feedback."""

    content_id: int
    user_id: int
    type: FeedbackType
