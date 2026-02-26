"""Command handlers for the Telegram bot."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()

_HELP_TEXT = """
🤖 *Alice — 智能信息秘书*

*可用命令：*
/start — 开始使用 Alice
/help — 显示帮助信息
/settings — 查看和修改设置
/status — 查看系统状态

*反馈按钮说明：*
👍高质量 — 内容有价值，已学到新知识
⏰稍后再看 — 加入待阅读队列
📖已知晓 — 内容已掌握
👎无价值 — 内容对我无用
❓解释概念 — 请 Alice 解释其中概念（即将推出）
💬追问 — 与 Alice 进行深度讨论（即将推出）

*更多功能即将推出，敬请期待！*
""".strip()

_START_TEXT = """
👋 你好！我是 *Alice*，你的 AI 信息秘书。

我会为你精选高质量的内容，并通过 Telegram 推送给你。每条推送都附有：
• 📋 核心内容摘要
• 🎯 推送原因
• 📖 阅读建议

你可以通过按钮反馈，帮助我更好地了解你的需求。

发送 /help 查看所有可用命令。
""".strip()


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    """Handle /start command — welcome message."""
    await message.answer(_START_TEXT, parse_mode="Markdown")


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Handle /help command — list commands."""
    await message.answer(_HELP_TEXT, parse_mode="Markdown")


@router.message(Command("settings"))
async def handle_settings(message: Message) -> None:
    """Handle /settings command — placeholder for Phase 2."""
    await message.answer(
        "⚙️ 设置功能即将推出。\n\n目前可通过反馈按钮（👍👎⏰📖）来训练你的个人偏好。",
        parse_mode="Markdown",
    )


@router.message(Command("status"))
async def handle_status(message: Message) -> None:
    """Handle /status command — system status."""
    await message.answer(
        "✅ *系统状态*\n\nAlice 运行正常，正在为你过滤和推送高质量内容。",
        parse_mode="Markdown",
    )
