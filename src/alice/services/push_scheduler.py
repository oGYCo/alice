"""Push scheduling logic — quiet hours, content windows, and frequency throttle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class PushSchedulerSettings:
    quiet_start: int = 23  # inclusive: hour >= quiet_start → quiet
    quiet_end: int = 7  # exclusive: hour < quiet_end → quiet
    push_frequency_per_day: int = 3
    timezone: str = "UTC"


class PushScheduler:
    def __init__(self, settings: PushSchedulerSettings | None = None) -> None:
        self.settings = settings or PushSchedulerSettings()

    def is_quiet_hours(self, dt: datetime) -> bool:
        """Return True when the given hour falls inside the configured quiet window."""
        h = dt.hour
        return h >= self.settings.quiet_start or h < self.settings.quiet_end

    def get_content_type_for_window(self, dt: datetime) -> str:
        """Return the preferred content category for the given time window."""
        # Weekend exploration regardless of hour
        if dt.weekday() >= 5:
            return "exploration"

        h = dt.hour
        if 8 <= h < 10:
            return "deep_knowledge"
        if 14 <= h < 16:
            return "practical"
        if 20 <= h < 23:
            return "thought_provoking"
        return "any"

    def should_push_now(self, dt: datetime, pushes_today: int) -> bool:
        """Return True only when outside quiet hours and under the daily push cap."""
        if self.is_quiet_hours(dt):
            return False
        if pushes_today >= self.settings.push_frequency_per_day:
            return False
        return True

    def get_timing_score(self, dt: datetime) -> float:
        """Return a 0–1 score reflecting how favourable *dt* is for pushing.

        * Quiet hours → 0.0  (suppress push entirely)
        * Named time window (deep_knowledge / practical / thought_provoking /
          exploration) → 1.0  (peak push time)
        * Active but outside a named window ("any") → 0.7
        """
        if self.is_quiet_hours(dt):
            return 0.0
        window = self.get_content_type_for_window(dt)
        if window == "any":
            return 0.7
        return 1.0

    def get_next_push_time(self, dt: datetime) -> datetime:
        """Return dt unchanged when active, or the next quiet_end boundary when quiet."""
        if not self.is_quiet_hours(dt):
            return dt

        quiet_end = self.settings.quiet_end

        # After-midnight portion of quiet window (e.g. 1am): wake up same day
        if dt.hour < self.settings.quiet_end:
            return dt.replace(hour=quiet_end, minute=0, second=0, microsecond=0)

        # Pre-midnight portion (e.g. 23:00): wake up next morning
        next_day = dt + timedelta(days=1)
        return next_day.replace(hour=quiet_end, minute=0, second=0, microsecond=0)
