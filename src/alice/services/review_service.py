"""Review card service — creates and manages FSRS-scheduled review cards.

Bridges the gap between user feedback and the FSRS spaced-repetition engine:
- On positive feedback, creates ReviewCards from content key_points/domains.
- On explicit review, records the review via FSRSEngine and updates the card.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.content import Content
from alice.models.review_card import CardState, ReviewCard
from alice.services.fsrs_engine import FSRSEngine, Rating

logger = logging.getLogger(__name__)

# Default initial stability for new cards (days)
_INITIAL_STABILITY = 1.0
# Default initial difficulty (mid-range on 1–10 scale)
_INITIAL_DIFFICULTY = 5.0


class ReviewCardService:
    """Manages ReviewCard lifecycle using FSRSEngine for scheduling."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._engine = FSRSEngine()

    async def create_cards_from_content(
        self,
        user_id: int,
        content_id: int,
    ) -> list[ReviewCard]:
        """Create ReviewCards for a content item's key concepts.

        Uses key_points as review prompts and domains as concept IDs.
        Skips concepts that already have a card for this user.
        Sets initial FSRS scheduling (due_date via FSRSEngine).

        Returns the list of newly created cards.
        """
        result = await self._session.execute(
            select(Content).where(Content.id == content_id)
        )
        content = result.scalar_one_or_none()
        if content is None:
            logger.warning("review_card_content_not_found", extra={"content_id": content_id})
            return []

        key_points: list[str] = content.key_points or []
        domains: list[str] = content.domains or []

        if not key_points and not domains:
            logger.debug(
                "review_card_no_concepts",
                extra={"content_id": content_id},
            )
            return []

        # Build concept→prompt pairs.
        # Each domain gets a card; prompt is the matching key_point (if available)
        # or a generic prompt derived from the content title.
        title = content.title or "Untitled"
        pairs: list[tuple[str, str]] = []

        if domains:
            for i, domain in enumerate(domains):
                prompt = key_points[i] if i < len(key_points) else f"回顾关于「{domain}」的知识点（来源：{title}）"
                pairs.append((domain, prompt))
        else:
            # No domains — use key_points directly as both concept and prompt
            for kp in key_points:
                concept_id = kp[:255]  # Truncate to fit column
                pairs.append((concept_id, kp))

        # Filter out concepts that already have cards for this user
        existing_concepts: set[str] = set()
        if pairs:
            concept_ids = [c for c, _ in pairs]
            existing_result = await self._session.execute(
                select(ReviewCard.concept_id).where(
                    ReviewCard.user_id == user_id,
                    ReviewCard.concept_id.in_(concept_ids),
                )
            )
            existing_concepts = {row[0] for row in existing_result.all()}

        now = datetime.now(UTC)
        created: list[ReviewCard] = []

        for concept_id, prompt in pairs:
            if concept_id in existing_concepts:
                continue

            # New card with FSRS initial scheduling
            due_date = now + timedelta(days=_INITIAL_STABILITY)
            card = ReviewCard(
                user_id=user_id,
                concept_id=concept_id,
                review_prompt=prompt,
                stability=_INITIAL_STABILITY,
                difficulty=_INITIAL_DIFFICULTY,
                due_date=due_date,
                state=CardState.new,
                reps=0,
                lapses=0,
            )
            self._session.add(card)
            created.append(card)

        if created:
            await self._session.flush()
            logger.info(
                "review_cards_created",
                extra={
                    "user_id": user_id,
                    "content_id": content_id,
                    "cards_created": len(created),
                    "skipped_existing": len(existing_concepts),
                },
            )

        return created

    async def record_review(
        self,
        card_id: int,
        rating: Rating,
    ) -> ReviewCard | None:
        """Record a review on an existing card using FSRSEngine.

        Computes new FSRS state (stability, difficulty, due_date, etc.)
        and persists the update. Returns the updated card, or None if not found.
        """
        result = await self._session.execute(
            select(ReviewCard).where(ReviewCard.id == card_id)
        )
        card = result.scalar_one_or_none()
        if card is None:
            logger.warning("review_card_not_found", extra={"card_id": card_id})
            return None

        updated = self._engine.record_review(card, rating)

        card.stability = updated.stability
        card.difficulty = updated.difficulty
        card.due_date = updated.due_date
        card.state = updated.state
        card.reps = updated.reps
        card.lapses = updated.lapses
        await self._session.flush()

        logger.info(
            "review_card_updated",
            extra={
                "card_id": card_id,
                "rating": rating.name,
                "new_state": updated.state,
                "new_stability": round(updated.stability, 4),
                "next_due": updated.due_date.isoformat(),
            },
        )
        return card

    async def get_due_cards(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[ReviewCard]:
        """Return cards due for review for the given user."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ReviewCard)
            .where(
                ReviewCard.user_id == user_id,
                (ReviewCard.due_date <= now) | (ReviewCard.due_date.is_(None)),
            )
            .order_by(ReviewCard.due_date.asc().nulls_first())
            .limit(limit)
        )
        return list(result.scalars().all())
