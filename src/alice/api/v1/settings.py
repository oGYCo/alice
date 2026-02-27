"""Settings API router — GET /settings/push, PUT /settings/push."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alice.db import get_db
from alice.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

ScheduleSlotName = Literal["morning", "work", "lunch", "evening", "late_night", "weekend"]
UserMode = Literal["daily", "project", "explore", "low_energy"]

DEFAULT_SCHEDULE: dict[ScheduleSlotName, dict[str, Any]] = {
    "morning": {
        "name": "morning",
        "start_time": "08:00",
        "end_time": "10:00",
        "is_enabled": True,
        "max_pushes": 2,
    },
    "work": {
        "name": "work",
        "start_time": "10:00",
        "end_time": "12:00",
        "is_enabled": False,
        "max_pushes": 0,
    },
    "lunch": {
        "name": "lunch",
        "start_time": "12:00",
        "end_time": "14:00",
        "is_enabled": True,
        "max_pushes": 3,
    },
    "evening": {
        "name": "evening",
        "start_time": "18:00",
        "end_time": "21:00",
        "is_enabled": True,
        "max_pushes": 5,
    },
    "late_night": {
        "name": "late_night",
        "start_time": "21:00",
        "end_time": "23:00",
        "is_enabled": True,
        "max_pushes": 2,
    },
    "weekend": {
        "name": "weekend",
        "start_time": "09:00",
        "end_time": "20:00",
        "is_enabled": True,
        "max_pushes": 10,
    },
}

PUSH_PREFERENCE_DEFAULTS: dict[str, Any] = {
    "quiet_start": 22,
    "quiet_end": 8,
    "max_per_day": 10,
    "preferred_types": [],
    "epsilon": 0.08,
    "user_mode": "daily",
    "project_description": None,
    "schedule": DEFAULT_SCHEDULE,
    "type_weights": {},
    "timezone": "UTC",
    "enabled": True,
}


class ScheduleSlotSchema(BaseModel):
    """Single push window slot settings."""

    name: ScheduleSlotName
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    is_enabled: bool = True
    max_pushes: int = Field(default=0, ge=0, le=50)


class PushPreferencesSchema(BaseModel):
    """Push notification preferences for a user."""

    user_id: int = Field(ge=1)
    quiet_start: int = Field(default=22, ge=0, le=23)
    quiet_end: int = Field(default=8, ge=0, le=23)
    max_per_day: int = Field(default=10, ge=1, le=50)
    preferred_types: list[str] = Field(default_factory=list)
    epsilon: float = Field(default=0.08, ge=0.0, le=1.0)
    user_mode: UserMode = "daily"
    project_description: str | None = None
    schedule: dict[ScheduleSlotName, ScheduleSlotSchema]
    type_weights: dict[str, float] = Field(default_factory=dict)
    timezone: str = Field(default="UTC", max_length=50)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_project_mode(self) -> "PushPreferencesSchema":
        """Project mode should have project context for better recommendations."""
        if self.user_mode == "project" and not self.project_description:
            self.project_description = ""
        return self


class PushPreferencesUpdateSchema(BaseModel):
    """Partial update schema for push preferences."""

    quiet_start: int | None = Field(default=None, ge=0, le=23)
    quiet_end: int | None = Field(default=None, ge=0, le=23)
    max_per_day: int | None = Field(default=None, ge=1, le=50)
    preferred_types: list[str] | None = None
    epsilon: float | None = Field(default=None, ge=0.0, le=1.0)
    user_mode: UserMode | None = None
    project_description: str | None = None
    schedule: dict[ScheduleSlotName, ScheduleSlotSchema] | None = None
    type_weights: dict[str, float] | None = None
    timezone: str | None = Field(default=None, max_length=50)
    enabled: bool | None = None


def _normalize_schedule(raw_schedule: Any) -> dict[ScheduleSlotName, ScheduleSlotSchema]:
    normalized: dict[ScheduleSlotName, ScheduleSlotSchema] = {}
    incoming = raw_schedule if isinstance(raw_schedule, dict) else {}
    for slot_name, slot_default in DEFAULT_SCHEDULE.items():
        raw_slot = incoming.get(slot_name, slot_default)
        if isinstance(raw_slot, ScheduleSlotSchema):
            merged_slot = raw_slot.model_dump()
        elif isinstance(raw_slot, dict):
            merged_slot = {**slot_default, **raw_slot}
        else:
            merged_slot = dict(slot_default)
        merged_slot["name"] = slot_name
        normalized[slot_name] = ScheduleSlotSchema(**merged_slot)
    return normalized


async def _get_or_create_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
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


def _extract_push_prefs(user_id: int, user: User) -> PushPreferencesSchema:
    """Extract push preferences from user.preferences, filling in defaults."""
    prefs = user.preferences if isinstance(user.preferences, dict) else {}
    merged = {**PUSH_PREFERENCE_DEFAULTS, **prefs}
    if "max_per_day" not in prefs and isinstance(prefs.get("push_frequency_per_day"), int):
        merged["max_per_day"] = prefs["push_frequency_per_day"]

    if merged.get("user_mode") not in {"daily", "project", "explore", "low_energy"}:
        merged["user_mode"] = PUSH_PREFERENCE_DEFAULTS["user_mode"]
    if not isinstance(merged.get("preferred_types"), list):
        merged["preferred_types"] = []
    if not isinstance(merged.get("type_weights"), dict):
        merged["type_weights"] = {}
    if not isinstance(merged.get("project_description"), str):
        merged["project_description"] = None

    merged["schedule"] = _normalize_schedule(merged.get("schedule"))
    merged["user_id"] = user_id
    return PushPreferencesSchema(
        **merged
    )


@router.get("/push", response_model=PushPreferencesSchema)
async def get_push_preferences(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Return push notification preferences for the given user."""
    user = await _get_or_create_user(user_id, session)
    return _extract_push_prefs(user_id, user)


@router.put("/push", response_model=PushPreferencesSchema)
async def update_push_preferences(
    user_id: int,
    update: PushPreferencesUpdateSchema,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Update push notification preferences for the given user."""
    user = await _get_or_create_user(user_id, session)
    current = _extract_push_prefs(user_id, user).model_dump()
    merged = {**current, **update.model_dump(exclude_none=True)}
    merged["schedule"] = _normalize_schedule(merged.get("schedule"))
    validated = PushPreferencesSchema(**merged)

    prefs_to_store = validated.model_dump(exclude={"user_id"})
    # Keep legacy key so older services using this key continue to work.
    prefs_to_store["push_frequency_per_day"] = validated.max_per_day
    user.preferences = prefs_to_store
    await session.commit()
    await session.refresh(user)
    return _extract_push_prefs(user_id, user)
