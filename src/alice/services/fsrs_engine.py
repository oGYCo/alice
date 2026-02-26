"""FSRS v5 Spaced Repetition Engine.

Free Spaced Repetition Scheduler implementation.
Core formula: R(t) = e^(-t/S)  where R=retention, t=elapsed days, S=stability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Protocol, cast

import structlog

from alice.models.review_card import CardState, ReviewCard


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


class Rating(IntEnum):
    """FSRS review rating."""

    again = 1  # Forgotten / failed
    hard = 2  # Correct but difficult
    good = 3  # Correct with some effort
    easy = 4  # Correct with ease


# Default intervals in days for the first review of a New card, keyed by rating
_NEW_CARD_INTERVALS: dict[Rating, float] = {
    Rating.again: 1.0,
    Rating.hard: 1.0,
    Rating.good: 3.0,
    Rating.easy: 7.0,
}

# Default initial stability values for a New card
_INITIAL_STABILITY: dict[Rating, float] = {
    Rating.again: 1.0,
    Rating.hard: 1.5,
    Rating.good: 3.0,
    Rating.easy: 7.0,
}

# Difficulty change deltas per rating
_DIFFICULTY_DELTA: dict[Rating, float] = {
    Rating.again: 0.2,
    Rating.hard: 0.1,
    Rating.good: 0.0,
    Rating.easy: -0.1,
}


@dataclass
class ReviewSchedule:
    """Output of schedule_review: the next optimal review time."""

    card_id: int
    next_review_date: datetime
    interval_days: float
    new_stability: float


@dataclass
class UpdatedCard:
    """Card state after a review event is recorded."""

    card_id: int
    stability: float
    difficulty: float
    due_date: datetime
    state: CardState
    reps: int
    lapses: int


class FSRSEngine:
    """Pure-logic FSRS v5 engine. No DB session — pass ReviewCard objects in.

    Usage:
        engine = FSRSEngine()
        schedule = engine.schedule_review(card)
        updated = engine.record_review(card, Rating.good)
    """

    # FSRS v5 default desired retention
    DESIRED_RETENTION: float = 0.9

    def schedule_review(self, card: ReviewCard) -> ReviewSchedule:
        """Compute the next optimal review schedule for a card without mutating it."""
        now = datetime.now(UTC)
        interval, stability = self._compute_interval_and_stability(card, Rating.good)
        next_review = now + timedelta(days=interval)
        return ReviewSchedule(
            card_id=card.id,
            next_review_date=next_review,
            interval_days=interval,
            new_stability=stability,
        )

    def record_review(self, card: ReviewCard, rating: Rating) -> UpdatedCard:
        """Compute new card state after a review. Returns an UpdatedCard (does not mutate card).

        State transitions:
            New      + any    → Learning (first exposure)
            Learning + Good/Easy → Review
            Learning + Again/Hard → stay Learning
            Review   + Good/Easy → Review (stability++)
            Review   + Again    → Relearning (lapse)
            Review   + Hard     → Review (stability*0.8)
            Relearning + Good/Easy → Review (graduated back)
            Relearning + Again  → Relearning (lapse again)
        """
        now = datetime.now(UTC)

        new_stability = self._update_stability(card, rating)
        new_difficulty = self._update_difficulty(card, rating)
        new_state, new_lapses = self._update_state(card, rating)
        new_reps = card.reps + 1
        interval = self._interval_for_stability(new_stability, new_state, rating, card)
        new_due = now + timedelta(days=interval)

        logger.debug(
            "fsrs_review_recorded",
            card_id=card.id,
            rating=rating.name,
            old_stability=round(card.stability, 4),
            new_stability=round(new_stability, 4),
            new_state=new_state,
            interval_days=round(interval, 2),
        )

        return UpdatedCard(
            card_id=card.id,
            stability=new_stability,
            difficulty=new_difficulty,
            due_date=new_due,
            state=new_state,
            reps=new_reps,
            lapses=new_lapses,
        )

    def retention_at(self, stability: float, days_elapsed: float) -> float:
        """R(t) = e^(-t/S) — probability of recall after t days."""
        if stability <= 0:
            return 0.0
        return math.exp(-days_elapsed / stability)

    def get_due_cards_filter(
        self, card_list: list[ReviewCard], user_id: int, limit: int = 20
    ) -> list[int]:
        """Return IDs of cards due for review (pure filter — no DB session).

        In production, the caller queries the DB and passes the loaded cards.
        """
        now = datetime.now(UTC)
        due = []
        for card in card_list:
            if card.user_id != user_id:
                continue
            if card.due_date is None:
                # New cards with no due date are always due
                due.append(card.id)
            else:
                due_date = card.due_date
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=UTC)
                if due_date <= now:
                    due.append(card.id)
            if len(due) >= limit:
                break
        return due

    # ── Private helpers ──────────────────────────────────────────────────────

    def _update_stability(self, card: ReviewCard, rating: Rating) -> float:
        """Compute new stability value based on current state and rating."""
        stability = card.stability
        difficulty = card.difficulty

        if card.state == CardState.new:
            # First time seeing the card
            return _INITIAL_STABILITY[rating]

        if rating == Rating.again:
            # Lapse: stability halved
            return max(0.1, stability * 0.5)

        if rating == Rating.hard:
            return max(0.1, stability * 0.8)

        # Good or Easy — stability increase
        # FSRS v5 simplified: S_new = S * e^(w * (1 - D/10)) * rating_factor
        # where w=0.9, rating_factor=1.0 for Good, 1.3 for Easy
        w = 0.9
        rating_factor = 1.0 if rating == Rating.good else 1.3
        new_s = stability * math.exp(w * (1.0 - difficulty / 10.0)) * rating_factor
        return max(0.1, new_s)

    def _update_difficulty(self, card: ReviewCard, rating: Rating) -> float:
        """Compute new difficulty. Clamped to [1.0, 10.0]."""
        delta = _DIFFICULTY_DELTA[rating]
        new_d = card.difficulty + delta
        return max(1.0, min(10.0, new_d))

    def _update_state(self, card: ReviewCard, rating: Rating) -> tuple[CardState, int]:
        """Return (new_state, new_lapses)."""
        lapses = card.lapses
        state = card.state

        if state == CardState.new:
            return CardState.learning, lapses

        if state == CardState.learning:
            if rating in (Rating.good, Rating.easy):
                return CardState.review, lapses
            return CardState.learning, lapses

        if state == CardState.review:
            if rating == Rating.again:
                return CardState.relearning, lapses + 1
            return CardState.review, lapses

        if state == CardState.relearning:
            if rating in (Rating.good, Rating.easy):
                return CardState.review, lapses
            return CardState.relearning, lapses + 1

        return state, lapses

    def _interval_for_stability(
        self,
        stability: float,
        new_state: CardState,
        rating: Rating,
        card: ReviewCard,
    ) -> float:
        """Compute interval in days for the next review."""
        if card.state == CardState.new:
            return _NEW_CARD_INTERVALS[rating]

        if new_state == CardState.learning:
            # Still in learning — short interval
            return 1.0

        if new_state == CardState.relearning:
            # Lapsed — reset to 1 day
            return 1.0

        # Review state: S is stability in days; interval = S gives ~37% retention
        # For practical spaced repetition, use S directly as days until next review
        interval = stability
        return max(1.0, interval)

    def _compute_interval_and_stability(
        self, card: ReviewCard, rating: Rating
    ) -> tuple[float, float]:
        """Helper used by schedule_review to get projected interval without recording."""
        new_stability = self._update_stability(card, rating)
        new_state, _ = self._update_state(card, rating)
        interval = self._interval_for_stability(new_stability, new_state, rating, card)
        return interval, new_stability
