"""Unit tests for UserStateManager — 4-mode state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alice.services.user_state import UserMode, UserStateManager


def _make_manager() -> UserStateManager:
    return UserStateManager()


class TestDefaultState:
    def test_default_is_daily(self):
        mgr = _make_manager()
        assert mgr.get_state(user_id=999) == UserMode.daily

    def test_new_user_no_crash(self):
        mgr = _make_manager()
        mode = mgr.get_state(user_id=1)
        assert isinstance(mode, UserMode)


class TestTransitions:
    def test_transition_to_project(self):
        mgr = _make_manager()
        result = mgr.transition(1, UserMode.project, {"topic": "CUDA kernel optimization"})
        assert result.success
        assert mgr.get_state(1) == UserMode.project

    def test_transition_to_explore(self):
        mgr = _make_manager()
        result = mgr.transition(1, UserMode.explore)
        assert result.new_mode == UserMode.explore

    def test_transition_to_low_energy(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.low_energy)
        assert mgr.get_state(1) == UserMode.low_energy

    def test_transition_records_old_mode(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.explore)
        result = mgr.transition(1, UserMode.daily)
        assert result.old_mode == UserMode.explore

    def test_reset_to_daily(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.project)
        mgr.reset_to_daily(1)
        assert mgr.get_state(1) == UserMode.daily


class TestPushModifiers:
    def test_project_mode_multiplier(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.project, {"topic": "CUDA kernel optimization"})
        mods = mgr.get_push_modifiers(1)
        assert mods.relevance_multiplier == 3.0

    def test_project_mode_pauses_non_related(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.project)
        mods = mgr.get_push_modifiers(1)
        assert mods.pause_non_related is True

    def test_explore_mode_cross_domain_boost(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.explore)
        mods = mgr.get_push_modifiers(1)
        assert mods.cross_domain_boost > 1.0

    def test_low_energy_mode_lightweight_only(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.low_energy)
        mods = mgr.get_push_modifiers(1)
        assert mods.lightweight_only is True

    def test_daily_mode_defaults(self):
        mgr = _make_manager()
        mods = mgr.get_push_modifiers(1)
        assert mods.relevance_multiplier == 1.0
        assert mods.pause_non_related is False


class TestAutoDetect:
    def test_late_night_returns_low_energy(self):
        mgr = _make_manager()
        t = datetime(2026, 3, 1, 23, 30, tzinfo=UTC)
        mode = mgr.auto_detect_mode(1, t)
        assert mode == UserMode.low_energy

    def test_early_morning_returns_low_energy(self):
        mgr = _make_manager()
        t = datetime(2026, 3, 2, 3, 0, tzinfo=UTC)
        mode = mgr.auto_detect_mode(1, t)
        assert mode == UserMode.low_energy

    def test_weekend_returns_explore(self):
        mgr = _make_manager()
        t = datetime(2026, 2, 28, 14, 0, tzinfo=UTC)  # Saturday
        mode = mgr.auto_detect_mode(1, t)
        assert mode == UserMode.explore

    def test_no_change_mid_week_daytime(self):
        mgr = _make_manager()
        t = datetime(2026, 3, 3, 10, 0, tzinfo=UTC)  # Tuesday
        mode = mgr.auto_detect_mode(1, t)
        assert mode is None


class TestInactiveAutoReset:
    def test_inactive_7_days_resets_to_daily(self):
        mgr = _make_manager()
        mgr.transition(1, UserMode.project)
        mgr._state_store[1]["last_active"] = datetime.now(UTC) - timedelta(days=8)
        assert mgr.get_state(1) == UserMode.daily
