"""Internationalization module for the Telegram bot.

Supports Chinese (zh) and English (en). Default language is Chinese.
User language preference is stored in ``User.preferences["language"]``.
"""

import logging

from aiogram import BaseMiddleware
from sqlalchemy import select

from alice.db import AsyncSessionLocal
from alice.models.user import User

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = ("zh", "en")
DEFAULT_LANGUAGE = "zh"

LANGUAGE_DISPLAY = {"zh": "中文", "en": "English"}

# ---------------------------------------------------------------------------
# Translation dictionaries
# ---------------------------------------------------------------------------

_ZH: dict[str, str] = {
    # /start
    "start_text": (
        "👋 你好！我是 *Alice*，你的 AI 信息秘书。\n\n"
        "我会为你精选高质量的内容，并通过 Telegram 推送给你。每条推送都附有：\n"
        "• 📋 核心内容摘要\n"
        "• 🎯 推送原因\n"
        "• 📖 阅读建议\n\n"
        "你可以通过按钮反馈，帮助我更好地了解你的需求。\n\n"
        "*快速上手：*\n"
        "• /push 立即获取推送\n"
        "• /review 复习已学知识\n"
        "• /help 查看所有命令"
    ),
    # /help
    "help_text": (
        "🤖 *Alice — 智能信息秘书*\n\n"
        "*信息推送：*\n"
        "/push — 主动获取推送（不等定时推送）\n"
        "/search `关键词` — 搜索已处理的内容\n\n"
        "*知识管理：*\n"
        "/review — 查看待复习的知识卡片\n"
        "/focus `主题` — 设置当前关注主题\n\n"
        "*系统管理：*\n"
        "/sources — 查看内容源列表\n"
        "/mode — 查看或切换推送模式\n"
        "/stats — 查看系统数据统计\n\n"
        "*其他：*\n"
        "/start — 开始使用\n"
        "/help — 查看命令列表\n"
        "/status — 系统运行状态\n"
        "/settings — 查看当前设置\n"
        "/lang — 切换语言\n\n"
        "*反馈按钮：*\n"
        "👍高质量 · ⏰稍后再看 · 📖已知晓 · 👎无价值\n"
        "❓解释概念 · 💬追问"
    ),
    # /push
    "push_empty": "📭 暂无新内容可推送。稍后再试或添加更多内容源。",
    "push_done": "✅ 已推送 {count} 条内容。",
    # /sources
    "sources_empty": "📡 暂无活跃的内容源。请通过 Web 界面添加。",
    "sources_header": "📡 *活跃内容源*\n",
    "sources_never": "从未",
    "sources_item": "• *{name}* ({type})\n  间隔: {interval}分钟 | 上次抓取: {last}",
    # /review
    "review_empty": "🎉 没有待复习的卡片，你已全部掌握！",
    "review_count": "📚 你有 {count} 张待复习卡片：",
    "review_btn_again": "❌ 忘了",
    "review_btn_hard": "😐 困难",
    "review_btn_good": "👍 记得",
    "review_btn_easy": "⚡ 简单",
    # /mode
    "mode_daily": "📋 日常模式",
    "mode_project": "🎯 项目模式",
    "mode_explore": "🔍 探索模式",
    "mode_low_energy": "😴 低能量模式",
    "mode_desc_daily": "均衡推送各类内容",
    "mode_desc_project": "聚焦项目相关内容，暂停跨领域推送",
    "mode_desc_explore": "增加跨领域推送，发现新知识",
    "mode_desc_low_energy": "仅推送轻量内容",
    "mode_current": "🔄 当前模式：{name}",
    "mode_invalid": "❌ 无效模式。可用值: {valid}",
    "mode_switched": "✅ 已切换到 {name}",
    # /focus
    "focus_usage": "用法：/focus `主题名称`\n例如：/focus transformer架构优化",
    "focus_set": (
        "🎯 已设置关注主题：*{topic}*\n"
        "已自动切换到项目模式，后续推送将优先关联此主题。"
    ),
    # /search
    "search_usage": "用法：/search `关键词`\n例如：/search attention mechanism",
    "search_error": "❌ 搜索服务暂时不可用，请稍后重试。",
    "search_empty": "🔍 未找到与「{query}」相关的内容。",
    "search_header": "🔍 搜索「{query}」找到 {total} 条结果：\n",
    "search_no_title": "(无标题)",
    # /stats
    "stats_header": "📊 *系统统计*\n",
    "stats_active_sources": "📡 活跃源: {count}",
    "stats_total_content": "📄 总内容: {count}",
    "stats_pushed": "\n📤 已推送: {count}",
    "stats_feedback": "💬 反馈数: {count}",
    "status_fetched": "已获取",
    "status_gatekept": "已筛选",
    "status_understood": "已理解",
    "status_scored": "已评分",
    "status_indexed": "已索引",
    "status_failed": "失败",
    # /status
    "system_status": (
        "✅ *系统状态*\n\n"
        "Alice 运行正常\n"
        "当前模式: {mode}\n\n"
        "发送 /stats 查看详细数据统计"
    ),
    # /settings
    "settings_header": "⚙️ *当前设置*\n",
    "settings_mode": "推送模式: {mode}",
    "settings_user_id": "用户 ID: {user_id}",
    "settings_language": "语言: {language}",
    "settings_prefs_header": "\n*偏好设置:*",
    "settings_prefs_item": "  • {key}: {value}",
    "settings_no_prefs": "\n_通过反馈按钮（👍👎⏰📖）训练个人偏好_",
    "settings_footer": "\n使用 /mode 切换模式 | /focus 设置关注主题 | /lang 切换语言",
    # /lang
    "lang_current": "🌐 当前语言：中文\n选择语言 / Select language:",
    "lang_switched": "✅ 语言已切换为中文。",
    "lang_zh_btn": "中文 🇨🇳",
    "lang_en_btn": "English 🇬🇧",
    # Feedback
    "feedback_valuable": "✅ 已记录！知识图谱已更新。",
    "feedback_later": "⏰ 已放入待阅读队列，稍后再看。",
    "feedback_not_valuable": "👎 已记录，将优化后续推送。",
    "feedback_known": "📖 了解了！已记录你的知识状态。",
    "feedback_invalid": "无效的反馈数据。",
    "feedback_recorded": "✅ 已记录！",
    # Review callback
    "review_again": "❌ 已标记为需要重新学习，稍后会再次出现。",
    "review_hard": "😐 已记录为困难，会较快再次复习。",
    "review_good": "👍 很好！下次复习时间已延长。",
    "review_easy": "⚡ 太棒了！已大幅延长复习间隔。",
    "review_invalid_data": "无效的复习数据。",
    "review_invalid_card": "无效的卡片 ID。",
    "review_invalid_rating": "无效的评分。",
    "review_not_found": "❌ 卡片未找到。",
    "review_next": "\n下次复习: {date}",
    "review_date_pending": "待定",
    "review_date_format": "%m月%d日",
    # Explain/Discuss
    "explain_coming": "❓ 解释概念功能即将推出，敬请期待！(Phase 4)",
    "discuss_coming": "💬 追问功能即将推出，敬请期待！(Phase 4)",
    # Common
    "invalid_operation": "无效操作。",
    "invalid_mode": "无效模式。",
    # Push card buttons
    "btn_quality": "👍高质量",
    "btn_later": "⏰稍后再看",
    "btn_known": "📖已知晓",
    "btn_not_valuable": "👎无价值",
    "btn_explain": "❓解释概念",
    "btn_discuss": "💬追问",
    "btn_acknowledged": "✅已了解",
    "btn_follow_up": "📌需要跟进",
    "btn_inspiring": "👍有启发",
    "btn_later_short": "⏰稍后",
    "btn_meh": "👎无感",
    "btn_discuss_short": "💬讨论",
}

_EN: dict[str, str] = {
    # /start
    "start_text": (
        "👋 Hi! I'm *Alice*, your AI information secretary.\n\n"
        "I curate high-quality content and deliver it via Telegram. "
        "Each push includes:\n"
        "• 📋 Core summary\n"
        "• 🎯 Push reason\n"
        "• 📖 Reading advice\n\n"
        "Use the feedback buttons to help me learn your preferences.\n\n"
        "*Quick Start:*\n"
        "• /push — Get content now\n"
        "• /review — Review learned knowledge\n"
        "• /help — View all commands"
    ),
    # /help
    "help_text": (
        "🤖 *Alice — AI Information Secretary*\n\n"
        "*Content:*\n"
        "/push — Fetch content now\n"
        "/search `keyword` — Search processed content\n\n"
        "*Knowledge:*\n"
        "/review — Review knowledge cards\n"
        "/focus `topic` — Set focus topic\n\n"
        "*System:*\n"
        "/sources — List content sources\n"
        "/mode — View or switch push mode\n"
        "/stats — System statistics\n\n"
        "*Other:*\n"
        "/start — Welcome message\n"
        "/help — Command list\n"
        "/status — System status\n"
        "/settings — Current settings\n"
        "/lang — Switch language\n\n"
        "*Feedback buttons:*\n"
        "👍 Quality · ⏰ Later · 📖 Known · 👎 Low Value\n"
        "❓ Explain · 💬 Discuss"
    ),
    # /push
    "push_empty": "📭 No new content to push. Try again later or add more sources.",
    "push_done": "✅ {count} item(s) pushed.",
    # /sources
    "sources_empty": "📡 No active content sources. Add via the web interface.",
    "sources_header": "📡 *Active Content Sources*\n",
    "sources_never": "Never",
    "sources_item": "• *{name}* ({type})\n  Interval: {interval}min | Last fetch: {last}",
    # /review
    "review_empty": "🎉 No cards due for review — you've mastered them all!",
    "review_count": "📚 You have {count} card(s) due for review:",
    "review_btn_again": "❌ Forgot",
    "review_btn_hard": "😐 Hard",
    "review_btn_good": "👍 Got it",
    "review_btn_easy": "⚡ Easy",
    # /mode
    "mode_daily": "📋 Daily",
    "mode_project": "🎯 Project",
    "mode_explore": "🔍 Explore",
    "mode_low_energy": "😴 Low Energy",
    "mode_desc_daily": "Balanced mix of all content types",
    "mode_desc_project": "Focus on project-related content, pause cross-domain",
    "mode_desc_explore": "More cross-domain content for discovery",
    "mode_desc_low_energy": "Lightweight content only",
    "mode_current": "🔄 Current mode: {name}",
    "mode_invalid": "❌ Invalid mode. Available: {valid}",
    "mode_switched": "✅ Switched to {name}",
    # /focus
    "focus_usage": "Usage: /focus `topic`\nExample: /focus transformer optimization",
    "focus_set": (
        "🎯 Focus set to: *{topic}*\n"
        "Switched to project mode. Future pushes will prioritize this topic."
    ),
    # /search
    "search_usage": "Usage: /search `keyword`\nExample: /search attention mechanism",
    "search_error": "❌ Search service temporarily unavailable. Please try later.",
    "search_empty": '🔍 No results found for "{query}".',
    "search_header": '🔍 Found {total} result(s) for "{query}":\n',
    "search_no_title": "(No title)",
    # /stats
    "stats_header": "📊 *System Statistics*\n",
    "stats_active_sources": "📡 Active sources: {count}",
    "stats_total_content": "📄 Total content: {count}",
    "stats_pushed": "\n📤 Pushed: {count}",
    "stats_feedback": "💬 Feedback: {count}",
    "status_fetched": "Fetched",
    "status_gatekept": "Gatekept",
    "status_understood": "Understood",
    "status_scored": "Scored",
    "status_indexed": "Indexed",
    "status_failed": "Failed",
    # /status
    "system_status": (
        "✅ *System Status*\n\n"
        "Alice is running normally\n"
        "Current mode: {mode}\n\n"
        "Send /stats for detailed statistics"
    ),
    # /settings
    "settings_header": "⚙️ *Current Settings*\n",
    "settings_mode": "Push mode: {mode}",
    "settings_user_id": "User ID: {user_id}",
    "settings_language": "Language: {language}",
    "settings_prefs_header": "\n*Preferences:*",
    "settings_prefs_item": "  • {key}: {value}",
    "settings_no_prefs": "\n_Train preferences via feedback buttons (👍👎⏰📖)_",
    "settings_footer": "\nUse /mode to switch mode | /focus to set topic | /lang to change language",
    # /lang
    "lang_current": "🌐 Current language: English\nSelect language / 选择语言:",
    "lang_switched": "✅ Language switched to English.",
    "lang_zh_btn": "中文 🇨🇳",
    "lang_en_btn": "English 🇬🇧",
    # Feedback
    "feedback_valuable": "✅ Recorded! Knowledge graph updated.",
    "feedback_later": "⏰ Added to reading queue for later.",
    "feedback_not_valuable": "👎 Recorded. Will optimize future pushes.",
    "feedback_known": "📖 Got it! Your knowledge state recorded.",
    "feedback_invalid": "Invalid feedback data.",
    "feedback_recorded": "✅ Recorded!",
    # Review callback
    "review_again": "❌ Marked for re-learning. Will appear again soon.",
    "review_hard": "😐 Recorded as hard. Will review again sooner.",
    "review_good": "👍 Great! Next review interval extended.",
    "review_easy": "⚡ Awesome! Review interval greatly extended.",
    "review_invalid_data": "Invalid review data.",
    "review_invalid_card": "Invalid card ID.",
    "review_invalid_rating": "Invalid rating.",
    "review_not_found": "❌ Card not found.",
    "review_next": "\nNext review: {date}",
    "review_date_pending": "TBD",
    "review_date_format": "%b %d",
    # Explain/Discuss
    "explain_coming": "❓ Explain Concept feature coming soon! (Phase 4)",
    "discuss_coming": "💬 Discussion feature coming soon! (Phase 4)",
    # Common
    "invalid_operation": "Invalid operation.",
    "invalid_mode": "Invalid mode.",
    # Push card buttons
    "btn_quality": "👍 Quality",
    "btn_later": "⏰ Later",
    "btn_known": "📖 Known",
    "btn_not_valuable": "👎 Low Value",
    "btn_explain": "❓ Explain",
    "btn_discuss": "💬 Discuss",
    "btn_acknowledged": "✅ Got it",
    "btn_follow_up": "📌 Follow up",
    "btn_inspiring": "👍 Inspiring",
    "btn_later_short": "⏰ Later",
    "btn_meh": "👎 Meh",
    "btn_discuss_short": "💬 Discuss",
}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": _ZH,
    "en": _EN,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: object) -> str:
    """Return the translated string for *key* in the given *lang*.

    If the key is missing for the requested language, falls back to Chinese.
    Keyword arguments are interpolated via ``str.format()``.
    """
    strings = _TRANSLATIONS.get(lang, _ZH)
    text = strings.get(key) or _ZH.get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            logger.warning("i18n format error: key=%s lang=%s kwargs=%s", key, lang, kwargs)
    return text


# ---------------------------------------------------------------------------
# Language helper
# ---------------------------------------------------------------------------


async def get_user_language(telegram_user_id: int) -> str:
    """Look up the preferred language for a Telegram user.

    Returns ``"zh"`` if the user is not found or has no preference.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.preferences).where(User.telegram_chat_id == telegram_user_id)
            )
            prefs = result.scalar_one_or_none()
            lang = (prefs or {}).get("language", DEFAULT_LANGUAGE)
            return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    except Exception:
        logger.debug("Failed to look up language for user %d", telegram_user_id, exc_info=True)
        return DEFAULT_LANGUAGE


async def set_user_language(telegram_user_id: int, lang: str) -> None:
    """Persist the language preference for a Telegram user.

    Creates the user row if it doesn't exist yet.
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {lang!r}")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_chat_id == telegram_user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                id=telegram_user_id,
                telegram_chat_id=telegram_user_id,
                preferences={"language": lang},
            )
            session.add(user)
        else:
            prefs = dict(user.preferences or {})
            prefs["language"] = lang
            user.preferences = prefs
        await session.commit()


# ---------------------------------------------------------------------------
# Aiogram middleware — injects ``lang`` into handler data
# ---------------------------------------------------------------------------


class LanguageMiddleware(BaseMiddleware):
    """Resolve the user's preferred language and inject it as ``lang``."""

    async def __call__(self, handler, event, data):  # type: ignore[override]
        user = getattr(event, "from_user", None)
        if user:
            data["lang"] = await get_user_language(user.id)
        else:
            data["lang"] = DEFAULT_LANGUAGE
        return await handler(event, data)
