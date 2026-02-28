"""Review card callback handler — processes FSRS review rating callbacks.

Callback data format: ``review:{card_id}:{rating}``
where *rating* is one of: again, hard, good, easy.
"""

import logging

from aiogram import Bot
from aiogram.types import CallbackQuery

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

_RATING_MESSAGES: dict[Rating, str] = {
    Rating.again: "❌ 已标记为需要重新学习，稍后会再次出现。",
    Rating.hard: "😐 已记录为困难，会较快再次复习。",
    Rating.good: "👍 很好！下次复习时间已延长。",
    Rating.easy: "⚡ 太棒了！已大幅延长复习间隔。",
}


async def handle_review_callback(query: CallbackQuery, bot: Bot) -> None:
    """Handle ``review:{card_id}:{rating}`` callback from review card buttons."""
    del bot  # reserved for future follow-up actions

    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "review":
        await query.answer(text="无效的复习数据。")
        return

    try:
        card_id = int(parts[1])
    except ValueError:
        await query.answer(text="无效的卡片 ID。")
        return

    rating_str = parts[2]
    rating = _RATING_MAP.get(rating_str)
    if rating is None:
        await query.answer(text="无效的评分。")
        return

    async with AsyncSessionLocal() as session:
        svc = ReviewCardService(session)
        card = await svc.record_review(card_id, rating)
        await session.commit()

    if card is None:
        await query.answer(text="❌ 卡片未找到。")
        return

    confirmation = _RATING_MESSAGES.get(rating, "✅ 已记录。")
    next_due = card.due_date.strftime("%m月%d日") if card.due_date else "待定"
    await query.answer(text=f"{confirmation}\n下次复习: {next_due}")

    logger.info(
        "review_recorded: card=%d rating=%s next_due=%s",
        card_id,
        rating_str,
        next_due,
    )
