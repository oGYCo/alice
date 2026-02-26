"""User mode state machine — 4 modes with auto-transitions and push modifiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.user import User


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

_AUTO_RESET_INACTIVE_DAYS = 7
_LOW_ENERGY_START_HOUR = 23
_LOW_ENERGY_END_HOUR = 7
_EXPLORE_WEEKEND_DAYS = {5, 6}  # Saturday, Sunday


class UserMode(StrEnum):
    """Four user operational modes."""

    daily = "daily"
    project = "project"
    explore = "explore"
    low_energy = "low_energy"


@dataclass
class PushModifiers:
    """Weight multipliers for the push scorer based on current user mode."""

    relevance_multiplier: float = 1.0
    pause_non_related: bool = False
    cross_domain_boost: float = 1.0
    lightweight_only: bool = False


@dataclass
class TransitionResult:
    """Result of a mode transition."""

    user_id: int
    old_mode: UserMode
    new_mode: UserMode
    success: bool
    context: dict = field(default_factory=dict)


class UserStateManager:
    """Manages user mode state with transitions and push modifiers."""

    def __init__(self) -> None:
        self._state_store: dict[int, dict] = {}

    def get_state(self, user_id: int) -> UserMode:
        """Return the current mode for a user (defaults to daily)."""
        entry = self._state_store.get(user_id)
        if entry is None:
            return UserMode.daily

        last_active = entry.get("last_active")
        if last_active is not None:
            idle_days = (datetime.now(UTC) - last_active).total_seconds() / 86400
            if idle_days >= _AUTO_RESET_INACTIVE_DAYS:
                self._state_store[user_id]["mode"] = UserMode.daily
                logger.info("auto_reset_to_daily", user_id=user_id, idle_days=round(idle_days, 1))

        return UserMode(entry.get("mode", UserMode.daily))

    def transition(
        self,
        user_id: int,
        target: UserMode,
        context: dict | None = None,
    ) -> TransitionResult:
        """Transition user to a new mode. Returns TransitionResult."""
        old_mode = self.get_state(user_id)
        ctx = context or {}

        self._state_store[user_id] = {
            "mode": target,
            "last_active": datetime.now(UTC),
            "context": ctx,
        }

        logger.info(
            "user_mode_transition",
            user_id=user_id,
            old_mode=old_mode,
            new_mode=target,
        )

        return TransitionResult(
            user_id=user_id,
            old_mode=old_mode,
            new_mode=target,
            success=True,
            context=ctx,
        )

    def get_push_modifiers(self, user_id: int) -> PushModifiers:
        """Return push weight multipliers for the current user mode."""
        mode = self.get_state(user_id)

        if mode == UserMode.project:
            return PushModifiers(
                relevance_multiplier=3.0,
                pause_non_related=True,
                cross_domain_boost=0.5,
                lightweight_only=False,
            )

        if mode == UserMode.explore:
            return PushModifiers(
                relevance_multiplier=0.8,
                pause_non_related=False,
                cross_domain_boost=2.0,
                lightweight_only=False,
            )

        if mode == UserMode.low_energy:
            return PushModifiers(
                relevance_multiplier=1.0,
                pause_non_related=False,
                cross_domain_boost=0.5,
                lightweight_only=True,
            )

        return PushModifiers()

    def auto_detect_mode(self, user_id: int, current_time: datetime) -> UserMode | None:
        """Detect whether to auto-transition based on time.

        Returns the suggested mode, or None if no change needed.
        Does NOT apply the transition — caller decides.
        """
        hour = current_time.hour
        weekday = current_time.weekday()
        current_mode = self.get_state(user_id)

        if hour >= _LOW_ENERGY_START_HOUR or hour < _LOW_ENERGY_END_HOUR:
            if current_mode != UserMode.low_energy:
                return UserMode.low_energy

        if weekday in _EXPLORE_WEEKEND_DAYS and current_mode == UserMode.daily:
            return UserMode.explore

        return None

    def reset_to_daily(self, user_id: int) -> TransitionResult:
        """Explicit reset to daily mode."""
        return self.transition(user_id, UserMode.daily)

    def touch(self, user_id: int) -> None:
        """Update last_active timestamp (called on any user interaction)."""
        if user_id in self._state_store:
            self._state_store[user_id]["last_active"] = datetime.now(UTC)
        else:
            self._state_store[user_id] = {
                "mode": UserMode.daily,
                "last_active": datetime.now(UTC),
                "context": {},
            }
