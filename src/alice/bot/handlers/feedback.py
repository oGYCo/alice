"""Feedback callback query handler — stores user feedback to PostgreSQL."""

import logging
from collections.abc import Callable
from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery
from sqlalchemy import select

from alice.bot.i18n import t
from alice.db import AsyncSessionLocal
from alice.models.feedback import Feedback
from alice.models.user import User
from alice.schemas.feedback import FeedbackType

logger = logging.getLogger(__name__)

# Mapping from callback data type strings to FeedbackType values
_FEEDBACK_TYPE_MAP: dict[str, FeedbackType] = {
    FeedbackType.valuable_learned: FeedbackType.valuable_learned,
    FeedbackType.save_for_later: FeedbackType.save_for_later,
    FeedbackType.not_valuable: FeedbackType.not_valuable,
    FeedbackType.already_known: FeedbackType.already_known,
}

# Human-readable confirmation messages per feedback type (i18n keys)
_FEEDBACK_I18N_KEYS: dict[FeedbackType, str] = {
    FeedbackType.valuable_learned: "feedback_valuable",
    FeedbackType.save_for_later: "feedback_later",
    FeedbackType.not_valuable: "feedback_not_valuable",
    FeedbackType.already_known: "feedback_known",
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


async def handle_feedback_callback(query: CallbackQuery, bot: Bot, *, lang: str = "zh") -> None:
    """Handle inline keyboard feedback callback.

    Parses callback data, stores Feedback record to DB, answers query.
    """
    del bot  # reserved for future bot-side follow-up actions
    await _handle_feedback_callback(query, session_factory=AsyncSessionLocal, lang=lang)


async def _handle_feedback_callback(
    query: CallbackQuery,
    *,
    session_factory: Callable[[], Any],
    lang: str = "zh",
) -> None:
    """Internal feedback handler with injectable DB session factory.

    Keeping session creation injectable allows integration tests to run against
    a real test database without patching module globals.
    """
    try:
        feedback_type, content_id = parse_callback_data(query.data)
    except ValueError:
        logger.warning("Invalid feedback callback data: %s", query.data)
        await query.answer(text=t("feedback_invalid", lang))
        return

    user_id = query.from_user.id

    async with session_factory() as session:
        # Look up user by telegram_chat_id (the stable Telegram identifier).
        # Existing users may have a different auto-incremented users.id.
        result = await session.execute(
            select(User).where(User.telegram_chat_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(id=user_id, telegram_chat_id=user_id, preferences={})
            session.add(user)
            await session.flush()

        db_user_id = user.id

        feedback = Feedback(
            content_id=content_id,
            user_id=db_user_id,
            type=feedback_type,
        )
        session.add(feedback)
        await session.commit()

        # Create FSRS review cards for positive feedback
        if feedback_type == FeedbackType.valuable_learned:
            try:
                from alice.services.review_service import ReviewCardService  # noqa: PLC0415

                svc = ReviewCardService(session)
                await svc.create_cards_from_content(db_user_id, content_id)
                await session.commit()
            except Exception:
                logger.warning(
                    "review_card_creation_failed: user=%d content=%d",
                    db_user_id,
                    content_id,
                    exc_info=True,
                )

    logger.info(
        "Feedback stored: telegram_user=%d content=%d type=%s",
        user_id,
        content_id,
        feedback_type,
    )

    confirmation_key = _FEEDBACK_I18N_KEYS.get(feedback_type, "feedback_recorded")
    await query.answer(text=t(confirmation_key, lang))


async def handle_feedback_callback_with_session_factory(
    query: CallbackQuery,
    bot: Bot,
    *,
    session_factory: Callable[[], Any],
    lang: str = "zh",
) -> None:
    """Public helper for tests to inject a real DB session factory."""
    del bot  # reserved for future bot-side follow-up actions
    await _handle_feedback_callback(query, session_factory=session_factory, lang=lang)


async def handle_explain_concept(query: CallbackQuery, bot: Bot, *, lang: str = "zh") -> None:
    """Placeholder handler for '解释概念' button (Phase 4 feature).

    Logs intent and replies with coming-soon message. No DB write.
    """
    logger.info("explain_concept requested by user=%d data=%s", query.from_user.id, query.data)
    await query.answer(text=t("explain_coming", lang))


async def handle_discuss(query: CallbackQuery, bot: Bot, *, lang: str = "zh") -> None:
    """Placeholder handler for '追问' button (Phase 4 feature).

    Logs intent and replies with coming-soon message. No DB write.
    """
    logger.info("discuss requested by user=%d data=%s", query.from_user.id, query.data)
    await query.answer(text=t("discuss_coming", lang))
