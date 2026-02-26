"""Settings API router — GET /settings/push, PUT /settings/push."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

PUSH_PREFERENCE_DEFAULTS: dict[str, Any] = {
    "quiet_start": 23,
    "quiet_end": 7,
    "push_frequency_per_day": 3,
    "timezone": "UTC",
    "enabled": True,
}


class PushPreferencesSchema(BaseModel):
    """Push notification preferences for a user."""

    quiet_start: int = Field(default=23, ge=0, le=23)
    quiet_end: int = Field(default=7, ge=0, le=23)
    push_frequency_per_day: int = Field(default=3, ge=1, le=10)
    timezone: str = Field(default="UTC", max_length=50)
    enabled: bool = True


class PushPreferencesUpdateSchema(BaseModel):
    """Partial update schema for push preferences."""

    quiet_start: int | None = Field(default=None, ge=0, le=23)
    quiet_end: int | None = Field(default=None, ge=0, le=23)
    push_frequency_per_day: int | None = Field(default=None, ge=1, le=10)
    timezone: str | None = Field(default=None, max_length=50)
    enabled: bool | None = None


async def _get_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _extract_push_prefs(user: User) -> PushPreferencesSchema:
    """Extract push preferences from user.preferences, filling in defaults."""
    prefs: dict[str, Any] = user.preferences or {}
    merged = {**PUSH_PREFERENCE_DEFAULTS, **prefs}
    return PushPreferencesSchema(
        quiet_start=merged["quiet_start"],
        quiet_end=merged["quiet_end"],
        push_frequency_per_day=merged["push_frequency_per_day"],
        timezone=merged["timezone"],
        enabled=merged["enabled"],
    )


@router.get("/push", response_model=PushPreferencesSchema)
async def get_push_preferences(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Return push notification preferences for the given user."""
    user = await _get_user(user_id, session)
    return _extract_push_prefs(user)


@router.put("/push", response_model=PushPreferencesSchema)
async def update_push_preferences(
    user_id: int,
    update: PushPreferencesUpdateSchema,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Update push notification preferences for the given user."""
    user = await _get_user(user_id, session)
    prefs: dict[str, Any] = dict(user.preferences or {})
    for field, value in update.model_dump(exclude_none=True).items():
        prefs[field] = value
    user.preferences = prefs
    await session.commit()
    await session.refresh(user)
    return _extract_push_prefs(user)
