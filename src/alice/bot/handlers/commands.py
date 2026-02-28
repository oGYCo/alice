"""Command handlers for the Telegram bot.

Provides all slash-command handlers registered on a single aiogram Router.
Each handler delegates to the appropriate service layer (push, source, review,
search, user-state …) through ``AsyncSessionLocal`` for DB access.
"""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from alice.bot.i18n import set_user_language, t
from alice.config import settings
from alice.db import AsyncSessionLocal
from alice.models.content import Content, PipelineStatus
from alice.models.feedback import Feedback
from alice.models.source import Source
from alice.models.user import User
from alice.services.memory_system import MemoryManager
from alice.services.push import PushService
from alice.services.review_service import ReviewCardService
from alice.services.source_service import SourceService
from alice.services.user_state import UserMode, get_user_state_manager

logger = logging.getLogger(__name__)

router = Router()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ensure_user(session, telegram_user_id: int) -> User:
    """Return the DB user for *telegram_user_id*, creating one if absent."""
    result = await session.execute(
        select(User).where(User.telegram_chat_id == telegram_user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=telegram_user_id, telegram_chat_id=telegram_user_id, preferences={})
        session.add(user)
        await session.flush()
    return user


def _parse_args(message: Message) -> str | None:
    """Extract everything after the first whitespace in the message text."""
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else None


# ---------------------------------------------------------------------------
# Mode display constants (shared with mode callback handler in main.py)
# ---------------------------------------------------------------------------

_MODE_I18N_KEYS: dict[UserMode, str] = {
    UserMode.daily: "daily",
    UserMode.project: "project",
    UserMode.explore: "explore",
    UserMode.low_energy: "low_energy",
}

# Legacy dicts kept for backward compatibility (Chinese only)
MODE_NAMES: dict[UserMode, str] = {
    UserMode.daily: "📋 日常模式",
    UserMode.project: "🎯 项目模式",
    UserMode.explore: "🔍 探索模式",
    UserMode.low_energy: "😴 低能量模式",
}

MODE_DESCRIPTIONS: dict[UserMode, str] = {
    UserMode.daily: "均衡推送各类内容",
    UserMode.project: "聚焦项目相关内容，暂停跨领域推送",
    UserMode.explore: "增加跨领域推送，发现新知识",
    UserMode.low_energy: "仅推送轻量内容",
}


def get_mode_name(mode: UserMode, lang: str = "zh") -> str:
    """Return localised display name for a mode."""
    key = _MODE_I18N_KEYS.get(mode, "daily")
    return t(f"mode_{key}", lang)


def get_mode_desc(mode: UserMode, lang: str = "zh") -> str:
    """Return localised description for a mode."""
    key = _MODE_I18N_KEYS.get(mode, "daily")
    return t(f"mode_desc_{key}", lang)

# ---------------------------------------------------------------------------
# Static text (now served via i18n)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


@router.message(Command("start"))
async def handle_start(message: Message, lang: str = "zh") -> None:
    """Welcome message."""
    await message.answer(t("start_text", lang), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------


@router.message(Command("help"))
async def handle_help(message: Message, lang: str = "zh") -> None:
    """List all available commands."""
    await message.answer(t("help_text", lang), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /push — 主动触发推送 (core feature)
# ---------------------------------------------------------------------------


@router.message(Command("push"))
async def handle_push(message: Message, lang: str = "zh") -> None:
    """Fetch and deliver the next batch of content to the user immediately."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    bot = message.bot

    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        db_user_id = user.id

        push_svc = PushService()
        batch = await push_svc.get_next_push_batch(session, db_user_id, limit=3)

        if not batch:
            await message.answer(t("push_empty", lang))
            return

        await push_svc.deliver_push(
            bot=bot,
            user_id=db_user_id,
            chat_id=chat_id,
            content_list=batch,
            session=session,
            lang=lang,
        )
        await message.answer(t("push_done", lang, count=len(batch)))


# ---------------------------------------------------------------------------
# /sources — 查看内容源
# ---------------------------------------------------------------------------


@router.message(Command("sources"))
async def handle_sources(message: Message, lang: str = "zh") -> None:
    """List active content sources."""
    async with AsyncSessionLocal() as session:
        svc = SourceService(session)
        sources = await svc.list_active()

    if not sources:
        await message.answer(t("sources_empty", lang))
        return

    lines = [t("sources_header", lang)]
    for s in sources:
        last = s.last_fetched_at.strftime("%m-%d %H:%M") if s.last_fetched_at else t("sources_never", lang)
        lines.append(
            t("sources_item", lang, name=s.name, type=s.type, interval=s.fetch_interval_minutes, last=last)
        )

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /review — 知识复习卡片
# ---------------------------------------------------------------------------


@router.message(Command("review"))
async def handle_review(message: Message, lang: str = "zh") -> None:
    """Show due review cards with FSRS rating buttons."""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        svc = ReviewCardService(session)
        cards = await svc.get_due_cards(user.id, limit=5)

    if not cards:
        await message.answer(t("review_empty", lang))
        return

    await message.answer(t("review_count", lang, count=len(cards)))

    for card in cards:
        text = f"💡 *{card.concept_id}*\n\n{card.review_prompt}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("review_btn_again", lang),
                        callback_data=f"review:{card.id}:again",
                    ),
                    InlineKeyboardButton(
                        text=t("review_btn_hard", lang),
                        callback_data=f"review:{card.id}:hard",
                    ),
                    InlineKeyboardButton(
                        text=t("review_btn_good", lang),
                        callback_data=f"review:{card.id}:good",
                    ),
                    InlineKeyboardButton(
                        text=t("review_btn_easy", lang),
                        callback_data=f"review:{card.id}:easy",
                    ),
                ]
            ]
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /mode [daily|project|explore|low_energy] — 查看/切换推送模式
# ---------------------------------------------------------------------------


@router.message(Command("mode"))
async def handle_mode(message: Message, lang: str = "zh") -> None:
    """Show current mode or switch to a new one."""
    user_id = message.from_user.id
    mgr = get_user_state_manager()
    args = _parse_args(message)

    if not args:
        # Show current mode with switch buttons
        current = mgr.get_state(user_id)
        name = get_mode_name(current, lang)
        desc = get_mode_desc(current, lang)

        lines = [t("mode_current", lang, name=name), f"_{desc}_\n"]
        for mode in UserMode:
            marker = " →" if mode == current else "  "
            lines.append(f"{marker} {get_mode_name(mode, lang)} — {get_mode_desc(mode, lang)}")

        keyboard_rows = [
            [InlineKeyboardButton(text=get_mode_name(m, lang), callback_data=f"mode:{m.value}")]
            for m in UserMode
            if m != current
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None
        await message.answer("\n".join(lines), reply_markup=markup, parse_mode="Markdown")
        return

    # Switch mode directly via argument
    target_str = args.lower()
    try:
        target = UserMode(target_str)
    except ValueError:
        valid = ", ".join(m.value for m in UserMode)
        await message.answer(t("mode_invalid", lang, valid=valid))
        return

    result = mgr.transition(user_id, target)
    name = get_mode_name(result.new_mode, lang)
    await message.answer(t("mode_switched", lang, name=name))


# ---------------------------------------------------------------------------
# /focus <topic> — 设置关注主题 (自动切换到 project 模式)
# ---------------------------------------------------------------------------


@router.message(Command("focus"))
async def handle_focus(message: Message, lang: str = "zh") -> None:
    """Set working-memory focus topic and switch to project mode."""
    topic = _parse_args(message)
    if not topic:
        await message.answer(t("focus_usage", lang), parse_mode="Markdown")
        return

    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        mm = MemoryManager()
        await mm.update_working_memory(session, user.id, declaration=topic)

    # Auto-switch to project mode
    mgr = get_user_state_manager()
    mgr.transition(user_id, UserMode.project, context={"focus_topic": topic})

    await message.answer(t("focus_set", lang, topic=topic), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /search <query> — 全文搜索
# ---------------------------------------------------------------------------


@router.message(Command("search"))
async def handle_search(message: Message, lang: str = "zh") -> None:
    """Full-text search across indexed content via Meilisearch."""
    query = _parse_args(message)
    if not query:
        await message.answer(t("search_usage", lang), parse_mode="Markdown")
        return

    from alice.services.search import SearchService  # noqa: PLC0415

    svc = SearchService(url=settings.MEILISEARCH_URL, api_key=settings.MEILISEARCH_API_KEY)
    try:
        result = svc.search(query, limit=5)
    except Exception:
        logger.exception("search_failed query=%s", query)
        await message.answer(t("search_error", lang))
        return

    hits = result.get("hits", [])
    if not hits:
        await message.answer(t("search_empty", lang, query=query))
        return

    total = result.get("estimatedTotalHits", len(hits))
    lines = [t("search_header", lang, query=query, total=total)]
    for hit in hits:
        title = hit.get("title") or t("search_no_title", lang)
        summary = hit.get("summary") or ""
        url = hit.get("source_url") or ""
        preview = (summary[:80] + "…") if len(summary) > 80 else summary
        lines.append(f"• *{title}*\n  {preview}\n  {url}\n")

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /stats — 系统数据统计
# ---------------------------------------------------------------------------


@router.message(Command("stats"))
async def handle_stats(message: Message, lang: str = "zh") -> None:
    """Show real system statistics from the database."""
    async with AsyncSessionLocal() as session:
        # Content counts by pipeline status
        status_result = await session.execute(
            select(Content.pipeline_status, func.count())
            .group_by(Content.pipeline_status)
        )
        status_counts = dict(status_result.all())
        total = sum(status_counts.values())

        # Pushed count
        pushed_result = await session.execute(
            select(func.count()).where(Content.pushed_at.isnot(None))
        )
        pushed = pushed_result.scalar() or 0

        # Active source count
        source_result = await session.execute(
            select(func.count()).select_from(Source).where(Source.is_active == True)  # noqa: E712
        )
        source_count = source_result.scalar() or 0

        # Feedback count
        feedback_result = await session.execute(
            select(func.count()).select_from(Feedback)
        )
        feedback_count = feedback_result.scalar() or 0

    status_i18n: dict[PipelineStatus, str] = {
        PipelineStatus.fetched: "status_fetched",
        PipelineStatus.gatekept: "status_gatekept",
        PipelineStatus.understood: "status_understood",
        PipelineStatus.scored: "status_scored",
        PipelineStatus.indexed: "status_indexed",
        PipelineStatus.failed: "status_failed",
    }

    lines = [
        t("stats_header", lang),
        t("stats_active_sources", lang, count=source_count),
        t("stats_total_content", lang, count=total),
    ]

    for status in PipelineStatus:
        count = status_counts.get(status, 0)
        if count > 0:
            label = t(status_i18n.get(status, "status_fetched"), lang)
            lines.append(f"  • {label}: {count}")

    lines.extend([
        t("stats_pushed", lang, count=pushed),
        t("stats_feedback", lang, count=feedback_count),
    ])

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /status — 系统运行状态
# ---------------------------------------------------------------------------


@router.message(Command("status"))
async def handle_status(message: Message, lang: str = "zh") -> None:
    """Show system running status and current user mode."""
    user_id = message.from_user.id
    mgr = get_user_state_manager()
    mode = mgr.get_state(user_id)
    mode_name = get_mode_name(mode, lang)

    await message.answer(
        t("system_status", lang, mode=mode_name),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /settings — 用户设置概览
# ---------------------------------------------------------------------------


@router.message(Command("settings"))
async def handle_settings(message: Message, lang: str = "zh") -> None:
    """Show current user settings and preferences."""
    user_id = message.from_user.id
    mgr = get_user_state_manager()
    mode = mgr.get_state(user_id)

    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        prefs = user.preferences or {}

    from alice.bot.i18n import LANGUAGE_DISPLAY  # noqa: PLC0415

    mode_name = get_mode_name(mode, lang)
    lang_display = LANGUAGE_DISPLAY.get(lang, lang)

    lines = [
        t("settings_header", lang),
        t("settings_mode", lang, mode=mode_name),
        t("settings_user_id", lang, user_id=user_id),
        t("settings_language", lang, language=lang_display),
    ]

    display_prefs = {k: v for k, v in prefs.items() if k != "language"}
    if display_prefs:
        lines.append(t("settings_prefs_header", lang))
        for k, v in display_prefs.items():
            lines.append(t("settings_prefs_item", lang, key=k, value=v))
    else:
        lines.append(t("settings_no_prefs", lang))

    lines.append(t("settings_footer", lang))

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /lang — 切换语言 / Switch language
# ---------------------------------------------------------------------------


@router.message(Command("lang"))
async def handle_lang(message: Message, lang: str = "zh") -> None:
    """Show language selector or switch directly via argument."""
    args = _parse_args(message)

    if args and args.lower() in ("zh", "en", "中文", "english"):
        target = "zh" if args.lower() in ("zh", "中文") else "en"
        await set_user_language(message.from_user.id, target)
        await message.answer(t("lang_switched", target))
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("lang_zh_btn", lang), callback_data="lang:zh"),
                InlineKeyboardButton(text=t("lang_en_btn", lang), callback_data="lang:en"),
            ]
        ]
    )
    await message.answer(t("lang_current", lang), reply_markup=keyboard)
