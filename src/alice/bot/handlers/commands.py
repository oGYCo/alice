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

# ---------------------------------------------------------------------------
# Static text
# ---------------------------------------------------------------------------

_HELP_TEXT = """
🤖 *Alice — 智能信息秘书*

*信息推送：*
/push — 主动获取推送（不等定时推送）
/search `关键词` — 搜索已处理的内容

*知识管理：*
/review — 查看待复习的知识卡片
/focus `主题` — 设置当前关注主题

*系统管理：*
/sources — 查看内容源列表
/mode — 查看或切换推送模式
/stats — 查看系统数据统计

*其他：*
/start — 开始使用
/help — 查看命令列表
/status — 系统运行状态
/settings — 查看当前设置

*反馈按钮：*
👍高质量 · ⏰稍后再看 · 📖已知晓 · 👎无价值
❓解释概念 · 💬追问
""".strip()

_START_TEXT = """
👋 你好！我是 *Alice*，你的 AI 信息秘书。

我会为你精选高质量的内容，并通过 Telegram 推送给你。每条推送都附有：
• 📋 核心内容摘要
• 🎯 推送原因
• 📖 阅读建议

你可以通过按钮反馈，帮助我更好地了解你的需求。

*快速上手：*
• /push 立即获取推送
• /review 复习已学知识
• /help 查看所有命令
""".strip()


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    """Welcome message."""
    await message.answer(_START_TEXT, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """List all available commands."""
    await message.answer(_HELP_TEXT, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /push — 主动触发推送 (core feature)
# ---------------------------------------------------------------------------


@router.message(Command("push"))
async def handle_push(message: Message) -> None:
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
            await message.answer("📭 暂无新内容可推送。稍后再试或添加更多内容源。")
            return

        await push_svc.deliver_push(
            bot=bot,
            user_id=db_user_id,
            chat_id=chat_id,
            content_list=batch,
            session=session,
        )
        await message.answer(f"✅ 已推送 {len(batch)} 条内容。")


# ---------------------------------------------------------------------------
# /sources — 查看内容源
# ---------------------------------------------------------------------------


@router.message(Command("sources"))
async def handle_sources(message: Message) -> None:
    """List active content sources."""
    async with AsyncSessionLocal() as session:
        svc = SourceService(session)
        sources = await svc.list_active()

    if not sources:
        await message.answer("📡 暂无活跃的内容源。请通过 Web 界面添加。")
        return

    lines = ["📡 *活跃内容源*\n"]
    for s in sources:
        last = s.last_fetched_at.strftime("%m-%d %H:%M") if s.last_fetched_at else "从未"
        lines.append(
            f"• *{s.name}* ({s.type})\n"
            f"  间隔: {s.fetch_interval_minutes}分钟 | 上次抓取: {last}"
        )

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /review — 知识复习卡片
# ---------------------------------------------------------------------------


@router.message(Command("review"))
async def handle_review(message: Message) -> None:
    """Show due review cards with FSRS rating buttons."""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        svc = ReviewCardService(session)
        cards = await svc.get_due_cards(user.id, limit=5)

    if not cards:
        await message.answer("🎉 没有待复习的卡片，你已全部掌握！")
        return

    await message.answer(f"📚 你有 {len(cards)} 张待复习卡片：")

    for card in cards:
        text = f"💡 *{card.concept_id}*\n\n{card.review_prompt}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ 忘了",
                        callback_data=f"review:{card.id}:again",
                    ),
                    InlineKeyboardButton(
                        text="😐 困难",
                        callback_data=f"review:{card.id}:hard",
                    ),
                    InlineKeyboardButton(
                        text="👍 记得",
                        callback_data=f"review:{card.id}:good",
                    ),
                    InlineKeyboardButton(
                        text="⚡ 简单",
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
async def handle_mode(message: Message) -> None:
    """Show current mode or switch to a new one."""
    user_id = message.from_user.id
    mgr = get_user_state_manager()
    args = _parse_args(message)

    if not args:
        # Show current mode with switch buttons
        current = mgr.get_state(user_id)
        name = MODE_NAMES.get(current, str(current))
        desc = MODE_DESCRIPTIONS.get(current, "")

        lines = [f"🔄 当前模式：{name}", f"_{desc}_\n"]
        for mode in UserMode:
            marker = " →" if mode == current else "  "
            lines.append(f"{marker} {MODE_NAMES[mode]} — {MODE_DESCRIPTIONS[mode]}")

        keyboard_rows = [
            [InlineKeyboardButton(text=MODE_NAMES[m], callback_data=f"mode:{m.value}")]
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
        await message.answer(f"❌ 无效模式。可用值: {valid}")
        return

    result = mgr.transition(user_id, target)
    name = MODE_NAMES.get(result.new_mode, str(result.new_mode))
    await message.answer(f"✅ 已切换到 {name}")


# ---------------------------------------------------------------------------
# /focus <topic> — 设置关注主题 (自动切换到 project 模式)
# ---------------------------------------------------------------------------


@router.message(Command("focus"))
async def handle_focus(message: Message) -> None:
    """Set working-memory focus topic and switch to project mode."""
    topic = _parse_args(message)
    if not topic:
        await message.answer(
            "用法：/focus `主题名称`\n例如：/focus transformer架构优化",
            parse_mode="Markdown",
        )
        return

    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        mm = MemoryManager()
        await mm.update_working_memory(session, user.id, declaration=topic)

    # Auto-switch to project mode
    mgr = get_user_state_manager()
    mgr.transition(user_id, UserMode.project, context={"focus_topic": topic})

    await message.answer(
        f"🎯 已设置关注主题：*{topic}*\n"
        f"已自动切换到项目模式，后续推送将优先关联此主题。",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /search <query> — 全文搜索
# ---------------------------------------------------------------------------


@router.message(Command("search"))
async def handle_search(message: Message) -> None:
    """Full-text search across indexed content via Meilisearch."""
    query = _parse_args(message)
    if not query:
        await message.answer(
            "用法：/search `关键词`\n例如：/search attention mechanism",
            parse_mode="Markdown",
        )
        return

    from alice.services.search import SearchService  # noqa: PLC0415

    svc = SearchService(url=settings.MEILISEARCH_URL, api_key=settings.MEILISEARCH_API_KEY)
    try:
        result = svc.search(query, limit=5)
    except Exception:
        logger.exception("search_failed query=%s", query)
        await message.answer("❌ 搜索服务暂时不可用，请稍后重试。")
        return

    hits = result.get("hits", [])
    if not hits:
        await message.answer(f"🔍 未找到与「{query}」相关的内容。")
        return

    total = result.get("estimatedTotalHits", len(hits))
    lines = [f"🔍 搜索「{query}」找到 {total} 条结果：\n"]
    for hit in hits:
        title = hit.get("title") or "(无标题)"
        summary = hit.get("summary") or ""
        url = hit.get("source_url") or ""
        preview = (summary[:80] + "…") if len(summary) > 80 else summary
        lines.append(f"• *{title}*\n  {preview}\n  {url}\n")

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /stats — 系统数据统计
# ---------------------------------------------------------------------------


@router.message(Command("stats"))
async def handle_stats(message: Message) -> None:
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

    _STATUS_LABELS = {
        PipelineStatus.fetched: "已获取",
        PipelineStatus.gatekept: "已筛选",
        PipelineStatus.understood: "已理解",
        PipelineStatus.scored: "已评分",
        PipelineStatus.indexed: "已索引",
        PipelineStatus.failed: "失败",
    }

    lines = [
        "📊 *系统统计*\n",
        f"📡 活跃源: {source_count}",
        f"📄 总内容: {total}",
    ]

    for status in PipelineStatus:
        count = status_counts.get(status, 0)
        if count > 0:
            label = _STATUS_LABELS.get(status, status)
            lines.append(f"  • {label}: {count}")

    lines.extend([
        f"\n📤 已推送: {pushed}",
        f"💬 反馈数: {feedback_count}",
    ])

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /status — 系统运行状态
# ---------------------------------------------------------------------------


@router.message(Command("status"))
async def handle_status(message: Message) -> None:
    """Show system running status and current user mode."""
    user_id = message.from_user.id
    mgr = get_user_state_manager()
    mode = mgr.get_state(user_id)
    mode_name = MODE_NAMES.get(mode, str(mode))

    await message.answer(
        f"✅ *系统状态*\n\n"
        f"Alice 运行正常\n"
        f"当前模式: {mode_name}\n\n"
        f"发送 /stats 查看详细数据统计",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /settings — 用户设置概览
# ---------------------------------------------------------------------------


@router.message(Command("settings"))
async def handle_settings(message: Message) -> None:
    """Show current user settings and preferences."""
    user_id = message.from_user.id
    mgr = get_user_state_manager()
    mode = mgr.get_state(user_id)

    async with AsyncSessionLocal() as session:
        user = await _ensure_user(session, user_id)
        prefs = user.preferences or {}

    mode_name = MODE_NAMES.get(mode, str(mode))

    lines = [
        "⚙️ *当前设置*\n",
        f"推送模式: {mode_name}",
        f"用户 ID: {user_id}",
    ]

    if prefs:
        lines.append("\n*偏好设置:*")
        for k, v in prefs.items():
            lines.append(f"  • {k}: {v}")
    else:
        lines.append("\n_通过反馈按钮（👍👎⏰📖）训练个人偏好_")

    lines.append("\n使用 /mode 切换模式 | /focus 设置关注主题")

    await message.answer("\n".join(lines), parse_mode="Markdown")
