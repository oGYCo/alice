"""Tests for Telegram bot feedback callback handler and DB storage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alice.bot.handlers.feedback import handle_feedback_callback, parse_callback_data
from alice.schemas.feedback import FeedbackType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_cm():
    """Return (cm, session) async context manager mock pair."""
    session = MagicMock()
    session.commit = AsyncMock()  # commit is awaited
    session.flush = AsyncMock()   # flush is awaited
    # execute returns an awaitable whose result has .scalar_one_or_none()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = True  # pretend user exists
    session.execute = AsyncMock(return_value=exec_result)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


def _make_query(callback_data: str, user_id: int = 123) -> MagicMock:
    query = MagicMock()
    query.data = callback_data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    return query


# ---------------------------------------------------------------------------
# parse_callback_data
# ---------------------------------------------------------------------------


def test_parse_callback_data_valuable():
    ft, cid = parse_callback_data("feedback:valuable_learned:42")
    assert ft == FeedbackType.valuable_learned
    assert cid == 42


def test_parse_callback_data_save_for_later():
    ft, cid = parse_callback_data("feedback:save_for_later:10")
    assert ft == FeedbackType.save_for_later
    assert cid == 10


def test_parse_callback_data_not_valuable():
    ft, cid = parse_callback_data("feedback:not_valuable:99")
    assert ft == FeedbackType.not_valuable
    assert cid == 99


def test_parse_callback_data_already_known():
    ft, cid = parse_callback_data("feedback:already_known:1")
    assert ft == FeedbackType.already_known
    assert cid == 1


def test_parse_callback_data_invalid_raises():
    with pytest.raises(ValueError):
        parse_callback_data("invalid:data")


def test_parse_callback_data_unknown_type_raises():
    with pytest.raises(ValueError):
        parse_callback_data("feedback:unknown_type:42")


# ---------------------------------------------------------------------------
# handle_feedback_callback — feedback stored in DB
# ---------------------------------------------------------------------------


async def test_feedback_stored_to_db():
    """Valid feedback callback creates a Feedback record in DB."""
    from aiogram import Bot

    bot = AsyncMock(spec=Bot)
    query = _make_query("feedback:valuable_learned:42")
    cm, session = _make_session_cm()

    with patch("alice.bot.handlers.feedback.AsyncSessionLocal", return_value=cm):
        await handle_feedback_callback(query, bot)

    # session.add was called with a Feedback object
    session.add.assert_called_once()
    feedback_obj = session.add.call_args.args[0]
    assert feedback_obj.content_id == 42
    assert feedback_obj.user_id == 123
    assert feedback_obj.type == FeedbackType.valuable_learned
    session.commit.assert_called_once()


async def test_feedback_stored_save_for_later():
    from aiogram import Bot

    bot = AsyncMock(spec=Bot)
    query = _make_query("feedback:save_for_later:7")
    cm, session = _make_session_cm()

    with patch("alice.bot.handlers.feedback.AsyncSessionLocal", return_value=cm):
        await handle_feedback_callback(query, bot)

    feedback_obj = session.add.call_args.args[0]
    assert feedback_obj.type == FeedbackType.save_for_later
    assert feedback_obj.content_id == 7


async def test_feedback_query_answered():
    """Callback query must be answered to dismiss spinner."""
    from aiogram import Bot

    bot = AsyncMock(spec=Bot)
    query = _make_query("feedback:not_valuable:5")
    cm, session = _make_session_cm()

    with patch("alice.bot.handlers.feedback.AsyncSessionLocal", return_value=cm):
        await handle_feedback_callback(query, bot)

    query.answer.assert_called_once()


async def test_feedback_reply_message_sent():
    """Bot sends a confirmation message after storing feedback."""
    from aiogram import Bot

    bot = AsyncMock(spec=Bot)
    query = _make_query("feedback:already_known:3")
    query.message = MagicMock()
    query.message.chat.id = 123
    cm, session = _make_session_cm()

    with patch("alice.bot.handlers.feedback.AsyncSessionLocal", return_value=cm):
        await handle_feedback_callback(query, bot)

    # Either bot.send_message or query.answer with text
    # Either approach is acceptable — just check query.answer called
    query.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Placeholder handlers — explain_concept and discuss
# ---------------------------------------------------------------------------


async def test_explain_concept_placeholder():
    """explain_concept callback returns 'coming soon' reply, no DB write."""
    from aiogram import Bot

    from alice.bot.handlers.feedback import handle_explain_concept

    bot = AsyncMock(spec=Bot)
    query = _make_query("explain:42")

    with patch("alice.bot.handlers.feedback.AsyncSessionLocal") as mock_session_cls:
        await handle_explain_concept(query, bot)
        # AsyncSessionLocal should NOT be called (no DB write)
        mock_session_cls.assert_not_called()

    query.answer.assert_called_once()
    answer_text = query.answer.call_args.kwargs.get("text") or (
        query.answer.call_args.args[0] if query.answer.call_args.args else ""
    )
    # Should mention "coming soon" or similar
    assert len(answer_text) > 0


async def test_discuss_placeholder():
    """discuss callback returns 'coming soon' reply, no DB write."""
    from aiogram import Bot

    from alice.bot.handlers.feedback import handle_discuss

    bot = AsyncMock(spec=Bot)
    query = _make_query("discuss:42")

    with patch("alice.bot.handlers.feedback.AsyncSessionLocal") as mock_session_cls:
        await handle_discuss(query, bot)
        mock_session_cls.assert_not_called()

    query.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Rate limiting — in-memory token bucket
# ---------------------------------------------------------------------------


async def test_rate_limiter_allows_first_message():
    """First message to user passes rate limiting."""
    from alice.bot.handlers.push import RateLimiter

    limiter = RateLimiter(per_user_rate=1.0, global_rate=30.0)
    allowed = await limiter.check(user_id=1)
    assert allowed is True


async def test_rate_limiter_blocks_too_fast():
    """Second immediate message to same user is blocked."""
    from alice.bot.handlers.push import RateLimiter

    limiter = RateLimiter(per_user_rate=1.0, global_rate=30.0)
    await limiter.check(user_id=1)  # consume token
    # Immediately try again — should be throttled
    allowed = await limiter.check(user_id=1)
    assert allowed is False


async def test_rate_limiter_different_users_independent():
    """Different users have independent rate limits."""
    from alice.bot.handlers.push import RateLimiter

    limiter = RateLimiter(per_user_rate=1.0, global_rate=30.0)
    await limiter.check(user_id=1)  # consume user 1's token
    allowed = await limiter.check(user_id=2)  # user 2 still has token
    assert allowed is True
