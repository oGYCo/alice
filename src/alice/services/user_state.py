"""User mode state machine — 4 modes with auto-transitions and push modifiers.

State is persisted to Redis when a ``redis_url`` is provided, falling back to
an in-process dict for unit testing or environments without Redis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast

import structlog


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

_AUTO_RESET_INACTIVE_DAYS = 7
_LOW_ENERGY_START_HOUR = 23
_LOW_ENERGY_END_HOUR = 7
_EXPLORE_WEEKEND_DAYS = {5, 6}  # Saturday, Sunday

_REDIS_KEY_PREFIX = "alice:user_state:"
_REDIS_KEY_TTL = 60 * 60 * 24 * 30  # 30 days


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


# ---------------------------------------------------------------------------
# State backend interface
# ---------------------------------------------------------------------------


class _StateBackend(Protocol):
    """Minimal sync interface for state persistence."""

    def get(self, user_id: int) -> dict | None: ...
    def set(self, user_id: int, data: dict) -> None: ...


class _InMemoryBackend:
    """In-memory backend (testing / fallback)."""

    def __init__(self) -> None:
        self._store: dict[int, dict] = {}

    def get(self, user_id: int) -> dict | None:
        return self._store.get(user_id)

    def set(self, user_id: int, data: dict) -> None:
        self._store[user_id] = data


class _RedisBackend:
    """Redis-backed state persistence."""

    def __init__(self, redis_url: str) -> None:
        import redis as _redis

        self._client: _redis.Redis = _redis.Redis.from_url(  # type: ignore[type-arg]
            redis_url, decode_responses=True
        )

    def get(self, user_id: int) -> dict | None:
        raw = self._client.get(f"{_REDIS_KEY_PREFIX}{user_id}")
        if raw is None:
            return None
        data: dict = json.loads(raw)
        # Restore datetime from ISO string
        la = data.get("last_active")
        if isinstance(la, str):
            data["last_active"] = datetime.fromisoformat(la)
        return data

    def set(self, user_id: int, data: dict) -> None:
        serializable = dict(data)
        la = serializable.get("last_active")
        if isinstance(la, datetime):
            serializable["last_active"] = la.isoformat()
        self._client.set(
            f"{_REDIS_KEY_PREFIX}{user_id}",
            json.dumps(serializable),
            ex=_REDIS_KEY_TTL,
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_singleton: UserStateManager | None = None


def get_user_state_manager(redis_url: str | None = None) -> UserStateManager:
    """Return a process-wide singleton ``UserStateManager``.

    On first call, if *redis_url* is provided (or ``REDIS_URL`` env-var is
    set), a Redis-backed instance is created.  Subsequent calls return the
    same instance regardless of arguments.
    """
    global _singleton  # noqa: PLW0603
    if _singleton is not None:
        return _singleton

    if redis_url is None:
        import os

        redis_url = os.environ.get("REDIS_URL")

    if redis_url:
        backend: _StateBackend = _RedisBackend(redis_url)
    else:
        backend = _InMemoryBackend()

    _singleton = UserStateManager(backend=backend)
    return _singleton


class UserStateManager:
    """Manages user mode state with transitions and push modifiers.

    Accepts an optional *backend* for state persistence.  When omitted an
    in-memory dict is used (suitable for tests).
    """

    def __init__(self, backend: _StateBackend | None = None) -> None:
        self._backend: _StateBackend = backend or _InMemoryBackend()

    # Expose _state_store for backward-compatible test access
    @property
    def _state_store(self) -> dict[int, dict]:
        """Legacy accessor — only works with in-memory backend."""
        if isinstance(self._backend, _InMemoryBackend):
            return self._backend._store
        raise AttributeError("_state_store is not available with Redis backend")

    def get_state(self, user_id: int) -> UserMode:
        """Return the current mode for a user (defaults to daily)."""
        entry = self._backend.get(user_id)
        if entry is None:
            return UserMode.daily

        last_active = entry.get("last_active")
        if last_active is not None:
            idle_days = (datetime.now(UTC) - last_active).total_seconds() / 86400
            if idle_days >= _AUTO_RESET_INACTIVE_DAYS:
                entry["mode"] = UserMode.daily
                self._backend.set(user_id, entry)
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

        self._backend.set(user_id, {
            "mode": target,
            "last_active": datetime.now(UTC),
            "context": ctx,
        })

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
        entry = self._backend.get(user_id)
        if entry is not None:
            entry["last_active"] = datetime.now(UTC)
            self._backend.set(user_id, entry)
        else:
            self._backend.set(user_id, {
                "mode": UserMode.daily,
                "last_active": datetime.now(UTC),
                "context": {},
            })
