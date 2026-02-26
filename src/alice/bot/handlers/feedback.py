"""Feedback callback query handler — stores user feedback to PostgreSQL."""

import logging

from aiogram import Bot
from aiogram.types import CallbackQuery

from alice.db import AsyncSessionLocal
from alice.models.feedback import Feedback
from alice.schemas.feedback import FeedbackType

logger = logging.getLogger(__name__)

# Mapping from callback data type strings to FeedbackType values
_FEEDBACK_TYPE_MAP: dict[str, FeedbackType] = {
    FeedbackType.valuable_learned: FeedbackType.valuable_learned,
    FeedbackType.save_for_later: FeedbackType.save_for_later,
    FeedbackType.not_valuable: FeedbackType.not_valuable,
    FeedbackType.already_known: FeedbackType.already_known,
}

# Human-readable confirmation messages per feedback type
_FEEDBACK_MESSAGES: dict[FeedbackType, str] = {
    FeedbackType.valuable_learned: "✅ 已记录！知识图谱已更新。",
    FeedbackType.save_for_later: "⏰ 已放入待阅读队列，稍后再看。",
    FeedbackType.not_valuable: "👎 已记录，将优化后续推送。",
    FeedbackType.already_known: "📖 了解了！已记录你的知识状态。",
}


def parse_callback_data(data: str) -> tuple[FeedbackType, int]:
    """Parse callback data string 'feedback:{type}:{content_id}'.

    Returns (FeedbackType, content_id).
    Raises ValueError for invalid format or unknown feedback type.
    """
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "feedback":
        raise ValueError(f"Invalid callback data format: {data!r}")

    type_str = parts[1]
    if type_str not in _FEEDBACK_TYPE_MAP:
        raise ValueError(f"Unknown feedback type: {type_str!r}")

    try:
        content_id = int(parts[2])
    except ValueError as exc:
        raise ValueError(f"Invalid content_id in callback data: {parts[2]!r}") from exc

    return _FEEDBACK_TYPE_MAP[type_str], content_id


async def handle_feedback_callback(query: CallbackQuery, bot: Bot) -> None:
    """Handle inline keyboard feedback callback.

    Parses callback data, stores Feedback record to DB, answers query.
    """
    try:
        feedback_type, content_id = parse_callback_data(query.data)
    except ValueError:
        logger.warning("Invalid feedback callback data: %s", query.data)
        await query.answer(text="无效的反馈数据。")
        return

    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        feedback = Feedback(
            content_id=content_id,
            user_id=user_id,
            type=feedback_type,
        )
        session.add(feedback)
        await session.commit()

    logger.info(
        "Feedback stored: user=%d content=%d type=%s",
        user_id,
        content_id,
        feedback_type,
    )

    confirmation = _FEEDBACK_MESSAGES.get(feedback_type, "✅ 已记录！")
    await query.answer(text=confirmation)


async def handle_explain_concept(query: CallbackQuery, bot: Bot) -> None:
    """Placeholder handler for '解释概念' button (Phase 4 feature).

    Logs intent and replies with coming-soon message. No DB write.
    """
    logger.info("explain_concept requested by user=%d data=%s", query.from_user.id, query.data)
    await query.answer(text="❓ 解释概念功能即将推出，敬请期待！(Phase 4)")


async def handle_discuss(query: CallbackQuery, bot: Bot) -> None:
    """Placeholder handler for '追问' button (Phase 4 feature).

    Logs intent and replies with coming-soon message. No DB write.
    """
    logger.info("discuss requested by user=%d data=%s", query.from_user.id, query.data)
    await query.answer(text="💬 追问功能即将推出，敬请期待！(Phase 4)")
