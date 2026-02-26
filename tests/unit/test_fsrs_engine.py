"""Unit tests for FSRSEngine — FSRS v5 spaced repetition algorithm."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from alice.models.review_card import CardState, ReviewCard
from alice.services.fsrs_engine import FSRSEngine, Rating, ReviewSchedule


def _make_card(
    card_id: int = 1,
    user_id: int = 42,
    state: CardState = CardState.new,
    stability: float = 1.0,
    difficulty: float = 5.0,
    due_date: datetime | None = None,
    reps: int = 0,
    lapses: int = 0,
) -> ReviewCard:
    card = MagicMock(spec=ReviewCard)
    card.id = card_id
    card.user_id = user_id
    card.state = state
    card.stability = stability
    card.difficulty = difficulty
    card.due_date = due_date
    card.reps = reps
    card.lapses = lapses
    return card


engine = FSRSEngine()


class TestNewCard:
    def test_new_card_good_becomes_learning(self):
        card = _make_card(state=CardState.new)
        updated = engine.record_review(card, Rating.good)
        assert updated.state == CardState.learning

    def test_new_card_again_becomes_learning(self):
        card = _make_card(state=CardState.new)
        updated = engine.record_review(card, Rating.again)
        assert updated.state == CardState.learning

    def test_new_card_good_interval_3_days(self):
        card = _make_card(state=CardState.new)
        updated = engine.record_review(card, Rating.good)
        now = datetime.now(UTC)
        delta = updated.due_date - now
        assert 2.5 < delta.total_seconds() / 86400 < 3.5

    def test_new_card_easy_interval_7_days(self):
        card = _make_card(state=CardState.new)
        updated = engine.record_review(card, Rating.easy)
        now = datetime.now(UTC)
        delta = updated.due_date - now
        assert 6.5 < delta.total_seconds() / 86400 < 7.5

    def test_new_card_reps_incremented(self):
        card = _make_card(state=CardState.new, reps=0)
        updated = engine.record_review(card, Rating.good)
        assert updated.reps == 1


class TestLearningCard:
    def test_learning_good_becomes_review(self):
        card = _make_card(state=CardState.learning, stability=3.0)
        updated = engine.record_review(card, Rating.good)
        assert updated.state == CardState.review

    def test_learning_easy_becomes_review(self):
        card = _make_card(state=CardState.learning, stability=3.0)
        updated = engine.record_review(card, Rating.easy)
        assert updated.state == CardState.review

    def test_learning_again_stays_learning(self):
        card = _make_card(state=CardState.learning, stability=3.0)
        updated = engine.record_review(card, Rating.again)
        assert updated.state == CardState.learning

    def test_learning_hard_stays_learning(self):
        card = _make_card(state=CardState.learning, stability=3.0)
        updated = engine.record_review(card, Rating.hard)
        assert updated.state == CardState.learning


class TestReviewCard:
    def test_review_good_stability_increases(self):
        card = _make_card(state=CardState.review, stability=5.0, difficulty=5.0)
        updated = engine.record_review(card, Rating.good)
        assert updated.stability > 5.0

    def test_review_good_due_date_future(self):
        card = _make_card(state=CardState.review, stability=5.0)
        updated = engine.record_review(card, Rating.good)
        now = datetime.now(UTC)
        assert updated.due_date > now + timedelta(days=1)

    def test_review_again_becomes_relearning(self):
        card = _make_card(state=CardState.review, stability=5.0)
        updated = engine.record_review(card, Rating.again)
        assert updated.state == CardState.relearning

    def test_review_again_increments_lapses(self):
        card = _make_card(state=CardState.review, stability=5.0, lapses=2)
        updated = engine.record_review(card, Rating.again)
        assert updated.lapses == 3

    def test_review_again_stability_decreases(self):
        card = _make_card(state=CardState.review, stability=5.0)
        updated = engine.record_review(card, Rating.again)
        assert updated.stability < 5.0

    def test_review_easy_large_interval(self):
        card = _make_card(state=CardState.review, stability=5.0)
        updated = engine.record_review(card, Rating.easy)
        now = datetime.now(UTC)
        delta = updated.due_date - now
        assert delta.total_seconds() / 86400 > 5.0


class TestRelearningCard:
    def test_relearning_good_becomes_review(self):
        card = _make_card(state=CardState.relearning, stability=1.0)
        updated = engine.record_review(card, Rating.good)
        assert updated.state == CardState.review

    def test_relearning_again_stays_relearning(self):
        card = _make_card(state=CardState.relearning, stability=1.0, lapses=1)
        updated = engine.record_review(card, Rating.again)
        assert updated.state == CardState.relearning
        assert updated.lapses == 2


class TestDifficultyBounds:
    def test_difficulty_caps_at_10(self):
        card = _make_card(state=CardState.review, difficulty=9.9)
        updated = engine.record_review(card, Rating.again)
        assert updated.difficulty <= 10.0

    def test_difficulty_floors_at_1(self):
        card = _make_card(state=CardState.review, difficulty=1.05)
        updated = engine.record_review(card, Rating.easy)
        assert updated.difficulty >= 1.0


class TestScheduleReview:
    def test_schedule_review_returns_schedule(self):
        card = _make_card(state=CardState.review, stability=5.0)
        schedule = engine.schedule_review(card)
        assert isinstance(schedule, ReviewSchedule)
        assert schedule.card_id == card.id
        assert schedule.interval_days > 0
        assert schedule.new_stability > 0

    def test_schedule_review_date_in_future(self):
        card = _make_card(state=CardState.review, stability=5.0)
        schedule = engine.schedule_review(card)
        assert schedule.next_review_date > datetime.now(UTC)


class TestStabilityAlwaysPositive:
    def test_stability_positive_after_many_lapses(self):
        card = _make_card(state=CardState.review, stability=0.2, lapses=10)
        for _ in range(5):
            updated = engine.record_review(card, Rating.again)
            card.stability = updated.stability
            card.state = updated.state
            card.lapses = updated.lapses
        assert updated.stability > 0


class TestRetention:
    def test_retention_formula(self):
        import math

        stability = 10.0
        days = 10.0
        expected = math.exp(-days / stability)
        assert abs(engine.retention_at(stability, days) - expected) < 1e-9

    def test_retention_zero_stability(self):
        assert engine.retention_at(0.0, 5.0) == 0.0


class TestDueCardsFilter:
    def test_due_cards_past_due(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        card = _make_card(card_id=1, user_id=1, due_date=past)
        result = engine.get_due_cards_filter([card], user_id=1)
        assert 1 in result

    def test_future_cards_not_due(self):
        future = datetime.now(UTC) + timedelta(days=1)
        card = _make_card(card_id=2, user_id=1, due_date=future)
        result = engine.get_due_cards_filter([card], user_id=1)
        assert 2 not in result

    def test_no_due_date_always_due(self):
        card = _make_card(card_id=3, user_id=1, due_date=None)
        result = engine.get_due_cards_filter([card], user_id=1)
        assert 3 in result

    def test_limit_respected(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        cards = [_make_card(card_id=i, user_id=1, due_date=past) for i in range(10)]
        result = engine.get_due_cards_filter(cards, user_id=1, limit=3)
        assert len(result) == 3
