"""Feedback API router — POST /feedback."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.models.content import Content
from alice.models.feedback import Feedback, FeedbackType
from alice.models.user import User

router = APIRouter(prefix="/feedback", tags=["feedback"])


FrontendFeedbackType = Literal[
    "positive",
    "negative",
    "seen",
    "save_for_later",
    "valuable_learned",
    "not_valuable",
    "already_known",
]

FEEDBACK_TYPE_MAP: dict[FrontendFeedbackType, FeedbackType] = {
    "positive": FeedbackType.valuable_learned,
    "negative": FeedbackType.not_valuable,
    "seen": FeedbackType.already_known,
    "save_for_later": FeedbackType.save_for_later,
    "valuable_learned": FeedbackType.valuable_learned,
    "not_valuable": FeedbackType.not_valuable,
    "already_known": FeedbackType.already_known,
}


class FeedbackCreateRequest(BaseModel):
    """Create feedback record for one user and one content item."""

    content_id: int = Field(ge=1)
    feedback_type: FrontendFeedbackType
    user_id: int = Field(default=1, ge=1)


class FeedbackResponse(BaseModel):
    """Feedback API response."""

    id: int
    content_id: int
    user_id: int
    type: FeedbackType
    created_at: datetime

    model_config = {"from_attributes": True}


async def _get_or_create_user(session: AsyncSession, user_id: int) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(id=user_id, telegram_chat_id=user_id, preferences={})
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Failed to initialize user {user_id}. "
                "Please verify users.telegram_chat_id uniqueness."
            ),
        ) from exc
    await session.refresh(user)
    return user


@router.post("", response_model=FeedbackResponse, status_code=201)
async def create_feedback(
    body: FeedbackCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Store frontend feedback for one content card."""
    feedback_type = FEEDBACK_TYPE_MAP[body.feedback_type]
    await _get_or_create_user(session, body.user_id)

    result = await session.execute(select(Content.id).where(Content.id == body.content_id))
    content_id = result.scalar_one_or_none()
    if content_id is None:
        raise HTTPException(status_code=404, detail=f"Content {body.content_id} not found")

    feedback = Feedback(
        content_id=body.content_id,
        user_id=body.user_id,
        type=feedback_type,
    )
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback
