"""Unit tests for PushScheduler.

TDD: tests written FIRST (RED), then implementation (GREEN).
All tests are synchronous — no asyncio needed.
"""

from __future__ import annotations

from datetime import datetime

from alice.services.push_scheduler import PushScheduler, PushSchedulerSettings

# ---------------------------------------------------------------------------
# PushSchedulerSettings
# ---------------------------------------------------------------------------


class TestPushSchedulerSettings:
    def test_default_settings(self):
        """Default settings should have sane push throttle defaults."""
        settings = PushSchedulerSettings()
        assert settings.quiet_start == 23
        assert settings.quiet_end == 7
        assert settings.push_frequency_per_day == 3
        assert settings.timezone == "UTC"

    def test_custom_settings(self):
        """Custom settings should override all defaults."""
        settings = PushSchedulerSettings(
            quiet_start=22,
            quiet_end=8,
            push_frequency_per_day=5,
            timezone="Asia/Shanghai",
        )
        assert settings.quiet_start == 22
        assert settings.quiet_end == 8
        assert settings.push_frequency_per_day == 5
        assert settings.timezone == "Asia/Shanghai"


# ---------------------------------------------------------------------------
# is_quiet_hours
# ---------------------------------------------------------------------------


class TestQuietHours:
    def test_quiet_at_1am(self):
        """1am is in quiet hours (after midnight, before 7am)."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 1, 0)
        assert sched.is_quiet_hours(dt) is True

    def test_quiet_at_3am(self):
        """3am is in quiet hours."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 3, 0)
        assert sched.is_quiet_hours(dt) is True

    def test_quiet_at_11pm(self):
        """11pm (23:00) is quiet hours start — should be quiet."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 23, 0)
        assert sched.is_quiet_hours(dt) is True

    def test_not_quiet_at_9am(self):
        """9am is after quiet hours end (7am) — should be active."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 9, 0)
        assert sched.is_quiet_hours(dt) is False

    def test_not_quiet_at_noon(self):
        """Noon is well outside quiet hours."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 12, 0)
        assert sched.is_quiet_hours(dt) is False

    def test_not_quiet_at_10pm(self):
        """10pm (22:00) is before quiet hours start (23:00) — active."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 22, 0)
        assert sched.is_quiet_hours(dt) is False

    def test_boundary_quiet_start(self):
        """Exactly at quiet_start hour (23:00) should be quiet."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 23, 0)
        assert sched.is_quiet_hours(dt) is True

    def test_boundary_quiet_end(self):
        """Exactly at quiet_end hour (7:00) should NOT be quiet (exclusive end)."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 7, 0)
        assert sched.is_quiet_hours(dt) is False


# ---------------------------------------------------------------------------
# get_content_type_for_window
# ---------------------------------------------------------------------------


class TestContentTypeForWindow:
    def test_weekday_morning(self):
        """Monday 9am falls in 8–10am window → deep_knowledge."""
        sched = PushScheduler()
        # 2026-02-23 is a Monday
        dt = datetime(2026, 2, 23, 9, 0)
        assert sched.get_content_type_for_window(dt) == "deep_knowledge"

    def test_weekday_afternoon(self):
        """Tuesday 3pm (15:00) falls in 14–16pm window → practical."""
        sched = PushScheduler()
        # 2026-02-24 is a Tuesday
        dt = datetime(2026, 2, 24, 15, 0)
        assert sched.get_content_type_for_window(dt) == "practical"

    def test_weekday_evening(self):
        """Wednesday 9pm (21:00) falls in 20–23pm window → thought_provoking."""
        sched = PushScheduler()
        # 2026-02-25 is a Wednesday
        dt = datetime(2026, 2, 25, 21, 0)
        assert sched.get_content_type_for_window(dt) == "thought_provoking"

    def test_weekend(self):
        """Saturday returns exploration regardless of hour."""
        sched = PushScheduler()
        # 2026-02-28 is a Saturday
        dt = datetime(2026, 2, 28, 10, 0)
        assert sched.get_content_type_for_window(dt) == "exploration"

    def test_other_time(self):
        """Weekday 11am doesn't match any specific window → any."""
        sched = PushScheduler()
        # 2026-02-23 is a Monday
        dt = datetime(2026, 2, 23, 11, 0)
        assert sched.get_content_type_for_window(dt) == "any"


# ---------------------------------------------------------------------------
# should_push_now
# ---------------------------------------------------------------------------


class TestShouldPushNow:
    def test_should_push_when_active_window_no_pushes(self):
        """9am weekday with 0 pushes today → should push."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 9, 0)
        assert sched.should_push_now(dt, pushes_today=0) is True

    def test_should_not_push_in_quiet_hours(self):
        """1am quiet hours → should not push regardless of count."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 1, 0)
        assert sched.should_push_now(dt, pushes_today=0) is False

    def test_should_not_push_when_frequency_exceeded(self):
        """Active window but pushes_today >= push_frequency_per_day → no push."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 9, 0)
        # Default push_frequency_per_day=3
        assert sched.should_push_now(dt, pushes_today=3) is False

    def test_should_push_at_limit_not_exceeded(self):
        """pushes_today=2 with default limit of 3 → still allowed."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 9, 0)
        assert sched.should_push_now(dt, pushes_today=2) is True


# ---------------------------------------------------------------------------
# get_next_push_time
# ---------------------------------------------------------------------------


class TestGetNextPushTime:
    def test_returns_now_when_not_quiet(self):
        """Active hours → returns the same datetime (push immediately)."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 9, 0)
        result = sched.get_next_push_time(dt)
        assert result == dt

    def test_returns_next_quiet_end_when_quiet_before_midnight(self):
        """11pm quiet → next push time should be 7am next day."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 23, 30)
        result = sched.get_next_push_time(dt)
        # Should be 7am on 2026-02-24
        assert result.hour == 7
        assert result.date() > dt.date()

    def test_returns_same_day_quiet_end_when_after_midnight(self):
        """1am quiet → next push time should be 7am same day."""
        sched = PushScheduler()
        dt = datetime(2026, 2, 23, 1, 0)
        result = sched.get_next_push_time(dt)
        # Should be 7am on the same day (2026-02-23)
        assert result.hour == 7
        assert result.date() == dt.date()
