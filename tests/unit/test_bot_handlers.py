"""Tests for Telegram bot message formatting, command handlers, and callbacks."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from alice.bot.handlers.commands import (
    handle_focus,
    handle_help,
    handle_mode,
    handle_push,
    handle_review,
    handle_search,
    handle_settings,
    handle_sources,
    handle_start,
    handle_stats,
    handle_status,
)
from alice.bot.handlers.push import build_push_card, send_push
from alice.bot.handlers.review import handle_review_callback
from alice.schemas.content import ContentResponseSchema
from alice.services.fsrs_engine import Rating
from alice.services.user_state import UserMode

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


def _make_message(text: str = "", user_id: int = 123) -> MagicMock:
    msg = MagicMock()
    msg.from_user.id = user_id
    msg.chat.id = user_id
    msg.text = text
    msg.answer = AsyncMock()
    msg.bot = AsyncMock()
    return msg


def _make_callback(data: str, user_id: int = 123) -> MagicMock:
    query = MagicMock()
    query.data = data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.edit_text = AsyncMock()
    return query


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
    msg = _make_message("/start")
    await handle_start(msg)
    msg.answer.assert_called_once()
    reply_text = msg.answer.call_args.args[0]
    assert len(reply_text) > 0


async def test_handle_start_mentions_alice():
    msg = _make_message("/start")
    await handle_start(msg)
    reply_text = msg.answer.call_args.args[0]
    assert "Alice" in reply_text or "alice" in reply_text.lower()


async def test_handle_start_mentions_push_command():
    msg = _make_message("/start")
    await handle_start(msg)
    reply_text = msg.answer.call_args.args[0]
    assert "/push" in reply_text


# ---------------------------------------------------------------------------
# Command handlers — /help
# ---------------------------------------------------------------------------


async def test_handle_help_replies():
    msg = _make_message("/help")
    await handle_help(msg)
    msg.answer.assert_called_once()


async def test_handle_help_lists_commands():
    msg = _make_message("/help")
    await handle_help(msg)
    reply_text = msg.answer.call_args.args[0]
    assert "/start" in reply_text
    assert "/help" in reply_text


async def test_handle_help_lists_new_commands():
    msg = _make_message("/help")
    await handle_help(msg)
    reply_text = msg.answer.call_args.args[0]
    assert "/push" in reply_text
    assert "/search" in reply_text
    assert "/review" in reply_text
    assert "/mode" in reply_text
    assert "/sources" in reply_text
    assert "/stats" in reply_text
    assert "/focus" in reply_text


# ---------------------------------------------------------------------------
# Command handlers — /push
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
@patch("alice.bot.handlers.commands.PushService")
async def test_handle_push_no_content(mock_push_cls, mock_session_local):
    """When no content is available, the user is informed."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock _ensure_user
    mock_user = MagicMock()
    mock_user.id = 123
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_user))

    # Mock PushService
    mock_push_svc = AsyncMock()
    mock_push_svc.get_next_push_batch = AsyncMock(return_value=[])
    mock_push_cls.return_value = mock_push_svc

    msg = _make_message("/push")
    await handle_push(msg)

    msg.answer.assert_called_once()
    reply = msg.answer.call_args.args[0]
    assert "暂无" in reply


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
@patch("alice.bot.handlers.commands.PushService")
async def test_handle_push_delivers_content(mock_push_cls, mock_session_local):
    """When content exists, deliver_push is called and user is notified."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 123
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_user))

    fake_batch = [MagicMock(), MagicMock()]
    mock_push_svc = AsyncMock()
    mock_push_svc.get_next_push_batch = AsyncMock(return_value=fake_batch)
    mock_push_svc.deliver_push = AsyncMock()
    mock_push_cls.return_value = mock_push_svc

    msg = _make_message("/push")
    await handle_push(msg)

    mock_push_svc.deliver_push.assert_called_once()
    reply = msg.answer.call_args.args[0]
    assert "2" in reply


# ---------------------------------------------------------------------------
# Command handlers — /sources
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
@patch("alice.bot.handlers.commands.SourceService")
async def test_handle_sources_empty(mock_svc_cls, mock_session_local):
    """When no active sources, user is informed."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_svc = AsyncMock()
    mock_svc.list_active = AsyncMock(return_value=[])
    mock_svc_cls.return_value = mock_svc

    msg = _make_message("/sources")
    await handle_sources(msg)

    reply = msg.answer.call_args.args[0]
    assert "暂无" in reply


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
@patch("alice.bot.handlers.commands.SourceService")
async def test_handle_sources_lists_sources(mock_svc_cls, mock_session_local):
    """Sources are listed with name and type."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    fake_source = MagicMock()
    fake_source.name = "HN"
    fake_source.type = "rss"
    fake_source.fetch_interval_minutes = 30
    fake_source.last_fetched_at = datetime(2026, 2, 28, 10, 0, 0)

    mock_svc = AsyncMock()
    mock_svc.list_active = AsyncMock(return_value=[fake_source])
    mock_svc_cls.return_value = mock_svc

    msg = _make_message("/sources")
    await handle_sources(msg)

    reply = msg.answer.call_args.args[0]
    assert "HN" in reply
    assert "rss" in reply


# ---------------------------------------------------------------------------
# Command handlers — /review
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
async def test_handle_review_no_cards(mock_session_local):
    """When no due cards, user gets congratulation message."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 123
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_user))

    with patch("alice.bot.handlers.commands.ReviewCardService") as mock_review_cls:
        mock_review_svc = AsyncMock()
        mock_review_svc.get_due_cards = AsyncMock(return_value=[])
        mock_review_cls.return_value = mock_review_svc

        msg = _make_message("/review")
        await handle_review(msg)

    # First call is the "没有待复习" message
    reply = msg.answer.call_args.args[0]
    assert "没有" in reply or "全部掌握" in reply


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
async def test_handle_review_shows_cards(mock_session_local):
    """Due cards are sent with inline rating buttons."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 123
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_user))

    fake_card = MagicMock()
    fake_card.id = 1
    fake_card.concept_id = "Transformer Attention"
    fake_card.review_prompt = "解释自注意力机制的核心思想"

    with patch("alice.bot.handlers.commands.ReviewCardService") as mock_review_cls:
        mock_review_svc = AsyncMock()
        mock_review_svc.get_due_cards = AsyncMock(return_value=[fake_card])
        mock_review_cls.return_value = mock_review_svc

        msg = _make_message("/review")
        await handle_review(msg)

    # Should have 2 calls: header + card
    assert msg.answer.call_count == 2
    card_call = msg.answer.call_args_list[1]
    card_text = card_call.args[0]
    assert "Transformer Attention" in card_text
    assert card_call.kwargs.get("reply_markup") is not None


# ---------------------------------------------------------------------------
# Command handlers — /mode
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.get_user_state_manager")
async def test_handle_mode_show_current(mock_get_mgr):
    """Without args, shows current mode and switch buttons."""
    mock_mgr = MagicMock()
    mock_mgr.get_state.return_value = UserMode.daily
    mock_get_mgr.return_value = mock_mgr

    msg = _make_message("/mode")
    await handle_mode(msg)

    reply = msg.answer.call_args.args[0]
    assert "日常模式" in reply
    assert msg.answer.call_args.kwargs.get("reply_markup") is not None


@patch("alice.bot.handlers.commands.get_user_state_manager")
async def test_handle_mode_switch(mock_get_mgr):
    """With valid mode arg, switches mode."""
    mock_mgr = MagicMock()
    mock_result = MagicMock()
    mock_result.new_mode = UserMode.explore
    mock_mgr.transition.return_value = mock_result
    mock_get_mgr.return_value = mock_mgr

    msg = _make_message("/mode explore")
    await handle_mode(msg)

    mock_mgr.transition.assert_called_once_with(123, UserMode.explore)
    reply = msg.answer.call_args.args[0]
    assert "探索模式" in reply


@patch("alice.bot.handlers.commands.get_user_state_manager")
async def test_handle_mode_invalid(mock_get_mgr):
    """Invalid mode arg shows error."""
    mock_get_mgr.return_value = MagicMock()

    msg = _make_message("/mode nonsense")
    await handle_mode(msg)

    reply = msg.answer.call_args.args[0]
    assert "无效" in reply


# ---------------------------------------------------------------------------
# Command handlers — /focus
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.get_user_state_manager")
@patch("alice.bot.handlers.commands.AsyncSessionLocal")
async def test_handle_focus_sets_topic(mock_session_local, mock_get_mgr):
    """Focus command sets working memory and switches to project mode."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 123
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_user))

    mock_mgr = MagicMock()
    mock_get_mgr.return_value = mock_mgr

    with patch("alice.bot.handlers.commands.MemoryManager") as mock_mm_cls:
        mock_mm = AsyncMock()
        mock_mm_cls.return_value = mock_mm

        msg = _make_message("/focus transformer优化")
        await handle_focus(msg)

    mock_mm.update_working_memory.assert_called_once()
    mock_mgr.transition.assert_called_once_with(
        123, UserMode.project, context={"focus_topic": "transformer优化"}
    )
    reply = msg.answer.call_args.args[0]
    assert "transformer优化" in reply
    assert "项目模式" in reply


async def test_handle_focus_no_args():
    """Focus without topic shows usage hint."""
    msg = _make_message("/focus")
    await handle_focus(msg)

    reply = msg.answer.call_args.args[0]
    assert "用法" in reply


# ---------------------------------------------------------------------------
# Command handlers — /search
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.settings")
async def test_handle_search_no_query(mock_settings):
    """Search without query shows usage hint."""
    msg = _make_message("/search")
    await handle_search(msg)

    reply = msg.answer.call_args.args[0]
    assert "用法" in reply


@patch("alice.bot.handlers.commands.settings")
async def test_handle_search_no_results(mock_settings):
    """Search with no hits informs the user."""
    mock_settings.MEILISEARCH_URL = "http://localhost:7700"
    mock_settings.MEILISEARCH_API_KEY = "testkey"

    with patch("alice.services.search.SearchService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.search.return_value = {"hits": [], "estimatedTotalHits": 0}
        mock_cls.return_value = mock_svc

        msg = _make_message("/search quantum computing")
        await handle_search(msg)

    reply = msg.answer.call_args.args[0]
    assert "未找到" in reply


@patch("alice.bot.handlers.commands.settings")
async def test_handle_search_with_results(mock_settings):
    """Search results are displayed with titles and previews."""
    mock_settings.MEILISEARCH_URL = "http://localhost:7700"
    mock_settings.MEILISEARCH_API_KEY = "testkey"

    hits = [
        {
            "title": "Quantum Error Correction",
            "summary": "A comprehensive overview of quantum error correction techniques.",
            "source_url": "https://example.com/quantum",
        }
    ]

    with patch("alice.services.search.SearchService") as mock_cls:
        mock_svc = MagicMock()
        mock_svc.search.return_value = {"hits": hits, "estimatedTotalHits": 1}
        mock_cls.return_value = mock_svc

        msg = _make_message("/search quantum")
        await handle_search(msg)

    reply = msg.answer.call_args.args[0]
    assert "Quantum Error Correction" in reply
    assert "example.com" in reply


# ---------------------------------------------------------------------------
# Command handlers — /stats
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.AsyncSessionLocal")
async def test_handle_stats_shows_counts(mock_session_local):
    """Stats command displays real database counts."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock 4 sequential DB queries
    mock_session.execute = AsyncMock(
        side_effect=[
            # status counts
            MagicMock(all=lambda: [("indexed", 10), ("fetched", 5)]),
            # pushed count
            MagicMock(scalar=lambda: 8),
            # source count
            MagicMock(scalar=lambda: 3),
            # feedback count
            MagicMock(scalar=lambda: 20),
        ]
    )

    msg = _make_message("/stats")
    await handle_stats(msg)

    reply = msg.answer.call_args.args[0]
    assert "系统统计" in reply
    assert "15" in reply  # total = 10 + 5
    assert "8" in reply  # pushed
    assert "3" in reply  # sources
    assert "20" in reply  # feedback


# ---------------------------------------------------------------------------
# Command handlers — /settings
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.get_user_state_manager")
@patch("alice.bot.handlers.commands.AsyncSessionLocal")
async def test_handle_settings_replies(mock_session_local, mock_get_mgr):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_user = MagicMock()
    mock_user.id = 123
    mock_user.preferences = {}
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_user))

    mock_mgr = MagicMock()
    mock_mgr.get_state.return_value = UserMode.daily
    mock_get_mgr.return_value = mock_mgr

    msg = _make_message("/settings")
    await handle_settings(msg)

    msg.answer.assert_called_once()
    reply = msg.answer.call_args.args[0]
    assert "设置" in reply
    assert "日常模式" in reply


# ---------------------------------------------------------------------------
# Command handlers — /status
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.commands.get_user_state_manager")
async def test_handle_status_replies(mock_get_mgr):
    mock_mgr = MagicMock()
    mock_mgr.get_state.return_value = UserMode.daily
    mock_get_mgr.return_value = mock_mgr

    msg = _make_message("/status")
    await handle_status(msg)

    msg.answer.assert_called_once()
    reply = msg.answer.call_args.args[0]
    assert "运行正常" in reply
    assert "日常模式" in reply


# ---------------------------------------------------------------------------
# Review callback handler
# ---------------------------------------------------------------------------


@patch("alice.bot.handlers.review.AsyncSessionLocal")
async def test_review_callback_records_rating(mock_session_local):
    """Valid review callback records the rating and responds."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    fake_card = MagicMock()
    fake_card.due_date = datetime(2026, 3, 5, tzinfo=UTC)

    with patch("alice.bot.handlers.review.ReviewCardService") as mock_cls:
        mock_svc = AsyncMock()
        mock_svc.record_review.return_value = fake_card
        mock_cls.return_value = mock_svc

        query = _make_callback("review:42:good")
        bot = AsyncMock()
        await handle_review_callback(query, bot)

    mock_svc.record_review.assert_called_once_with(42, Rating.good)
    query.answer.assert_called_once()
    reply = query.answer.call_args.kwargs["text"]
    assert "03月05日" in reply


@patch("alice.bot.handlers.review.AsyncSessionLocal")
async def test_review_callback_invalid_rating(mock_session_local):
    """Invalid rating string is rejected."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

    query = _make_callback("review:42:invalid")
    bot = AsyncMock()
    await handle_review_callback(query, bot)

    query.answer.assert_called_once()
    reply = query.answer.call_args.kwargs["text"]
    assert "无效" in reply


async def test_review_callback_bad_format():
    """Malformed callback data is rejected."""
    query = _make_callback("review:baddata")
    bot = AsyncMock()
    await handle_review_callback(query, bot)

    query.answer.assert_called_once()
    reply = query.answer.call_args.kwargs["text"]
    assert "无效" in reply
