"""Review card callback handler — processes FSRS review rating callbacks.

Callback data format: ``review:{card_id}:{rating}``
where *rating* is one of: again, hard, good, easy.
"""

import logging

from aiogram import Bot
from aiogram.types import CallbackQuery

from alice.bot.i18n import t
from alice.db import AsyncSessionLocal
from alice.services.fsrs_engine import Rating
from alice.services.review_service import ReviewCardService

logger = logging.getLogger(__name__)

_RATING_MAP: dict[str, Rating] = {
    "again": Rating.again,
    "hard": Rating.hard,
    "good": Rating.good,
    "easy": Rating.easy,
}

_RATING_I18N_KEYS: dict[Rating, str] = {
    Rating.again: "review_again",
    Rating.hard: "review_hard",
    Rating.good: "review_good",
    Rating.easy: "review_easy",
}


async def handle_review_callback(query: CallbackQuery, bot: Bot, *, lang: str = "zh") -> None:
    """Handle ``review:{card_id}:{rating}`` callback from review card buttons."""
    del bot  # reserved for future follow-up actions

    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "review":
        await query.answer(text=t("review_invalid_data", lang))
        return

    try:
        card_id = int(parts[1])
    except ValueError:
        await query.answer(text=t("review_invalid_card", lang))
        return

    rating_str = parts[2]
    rating = _RATING_MAP.get(rating_str)
    if rating is None:
        await query.answer(text=t("review_invalid_rating", lang))
        return

    async with AsyncSessionLocal() as session:
        svc = ReviewCardService(session)
        card = await svc.record_review(card_id, rating)
        await session.commit()

    if card is None:
        await query.answer(text=t("review_not_found", lang))
        return

    confirmation_key = _RATING_I18N_KEYS.get(rating, "review_good")
    confirmation = t(confirmation_key, lang)
    date_fmt = t("review_date_format", lang)
    next_due = card.due_date.strftime(date_fmt) if card.due_date else t("review_date_pending", lang)
    await query.answer(text=f"{confirmation}{t('review_next', lang, date=next_due)}")

    logger.info(
        "review_recorded: card=%d rating=%s next_due=%s",
        card_id,
        rating_str,
        next_due,
    )
