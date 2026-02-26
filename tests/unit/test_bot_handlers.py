"""Tests for Telegram bot message formatting and command handlers."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from alice.bot.handlers.commands import (
    handle_help,
    handle_settings,
    handle_start,
    handle_status,
)
from alice.bot.handlers.push import build_push_card, send_push
from alice.schemas.content import ContentResponseSchema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> ContentResponseSchema:
    defaults = dict(
        id=42,
        source="rss",
        source_url="https://example.com/article",
        title="FlashAttention-3: Hardware Async Acceleration",
        pipeline_status="indexed",
        quality_score=0.92,
        summary="This paper proposes FlashAttention-3 leveraging GPU async to reach 75% peak throughput on H100.",
        key_points=["Hardware async overlap", "TMA data movement", "75% peak throughput"],
        domains=["AI", "GPU"],
        estimated_read_time=12,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    defaults.update(kwargs)
    return ContentResponseSchema(**defaults)


def _make_message() -> MagicMock:
    msg = MagicMock()
    msg.from_user.id = 123
    msg.answer = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# Card formatting
# ---------------------------------------------------------------------------


def test_build_push_card_contains_title():
    content = _make_content()
    text, markup = build_push_card(content)
    assert content.title in text


def test_build_push_card_contains_summary():
    content = _make_content()
    text, markup = build_push_card(content)
    assert content.summary in text


def test_build_push_card_contains_read_time():
    content = _make_content()
    text, markup = build_push_card(content)
    assert "12" in text


def test_build_push_card_contains_key_points():
    content = _make_content()
    text, markup = build_push_card(content)
    assert "Hardware async overlap" in text


def test_build_push_card_contains_source_url():
    content = _make_content()
    text, markup = build_push_card(content)
    assert content.source_url in text


def test_build_push_card_returns_markup_with_6_buttons():
    content = _make_content()
    text, markup = build_push_card(content)
    # InlineKeyboardMarkup — flatten all rows to count buttons
    button_count = sum(len(row) for row in markup.inline_keyboard)
    assert button_count == 6


def test_build_push_card_button_callbacks_contain_content_id():
    content = _make_content()
    text, markup = build_push_card(content)
    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    for btn in all_buttons:
        if btn.callback_data and btn.callback_data.startswith("feedback:"):
            assert "42" in btn.callback_data


def test_build_push_card_button_labels():
    content = _make_content()
    text, markup = build_push_card(content)
    all_labels = [btn.text for row in markup.inline_keyboard for btn in row]
    labels_text = " ".join(all_labels)
    assert "👍" in labels_text
    assert "⏰" in labels_text
    assert "📖" in labels_text
    assert "👎" in labels_text
    assert "❓" in labels_text
    assert "💬" in labels_text


def test_build_push_card_callback_format():
    """All feedback buttons must use feedback:{type}:{content_id} format."""
    content = _make_content()
    text, markup = build_push_card(content)
    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    feedback_buttons = [
        b for b in all_buttons if b.callback_data and b.callback_data.startswith("feedback:")
    ]
    # There should be at least 4 feedback buttons (the ones that store to DB)
    assert len(feedback_buttons) >= 4
    for btn in feedback_buttons:
        parts = btn.callback_data.split(":")
        assert len(parts) == 3
        assert parts[0] == "feedback"
        assert parts[2] == "42"


def test_build_push_card_with_no_key_points():
    """Card handles None key_points gracefully."""
    content = _make_content(key_points=None)
    text, markup = build_push_card(content)
    assert content.title in text


def test_build_push_card_with_no_title():
    """Card handles None title gracefully."""
    content = _make_content(title=None)
    text, markup = build_push_card(content)
    assert content.summary in text


# ---------------------------------------------------------------------------
# send_push
# ---------------------------------------------------------------------------


async def test_send_push_calls_bot_send_message():
    from aiogram import Bot

    bot = AsyncMock(spec=Bot)
    content = _make_content()
    await send_push(bot=bot, chat_id=123, content=content)
    bot.send_message.assert_called_once()
    call_kwargs = bot.send_message.call_args
    assert call_kwargs.kwargs["chat_id"] == 123 or call_kwargs.args[0] == 123


async def test_send_push_passes_markup():
    from aiogram import Bot

    bot = AsyncMock(spec=Bot)
    content = _make_content()
    await send_push(bot=bot, chat_id=123, content=content)
    call_kwargs = bot.send_message.call_args
    # reply_markup should be present
    assert call_kwargs.kwargs.get("reply_markup") is not None


# ---------------------------------------------------------------------------
# Command handlers — /start
# ---------------------------------------------------------------------------


async def test_handle_start_replies():
    msg = _make_message()
    await handle_start(msg)
    msg.answer.assert_called_once()
    reply_text = msg.answer.call_args.args[0]
    assert len(reply_text) > 0


async def test_handle_start_mentions_alice():
    msg = _make_message()
    await handle_start(msg)
    reply_text = msg.answer.call_args.args[0]
    assert "Alice" in reply_text or "alice" in reply_text.lower()


# ---------------------------------------------------------------------------
# Command handlers — /help
# ---------------------------------------------------------------------------


async def test_handle_help_replies():
    msg = _make_message()
    await handle_help(msg)
    msg.answer.assert_called_once()


async def test_handle_help_lists_commands():
    msg = _make_message()
    await handle_help(msg)
    reply_text = msg.answer.call_args.args[0]
    assert "/start" in reply_text or "/help" in reply_text


# ---------------------------------------------------------------------------
# Command handlers — /settings
# ---------------------------------------------------------------------------


async def test_handle_settings_replies():
    msg = _make_message()
    await handle_settings(msg)
    msg.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Command handlers — /status
# ---------------------------------------------------------------------------


async def test_handle_status_replies():
    msg = _make_message()
    await handle_status(msg)
    msg.answer.assert_called_once()
