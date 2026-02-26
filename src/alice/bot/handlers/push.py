"""Push notification formatting and delivery with rate limiting."""

import asyncio
import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from alice.schemas.content import ContentResponseSchema
from alice.schemas.feedback import FeedbackType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Button definitions — maps display text to callback data type
# ---------------------------------------------------------------------------

_FEEDBACK_BUTTONS: list[tuple[str, str]] = [
    ("👍高质量", FeedbackType.valuable_learned),
    ("⏰稍后再看", FeedbackType.save_for_later),
    ("📖已知晓", FeedbackType.already_known),
    ("👎无价值", FeedbackType.not_valuable),
]

_EXTRA_BUTTONS: list[tuple[str, str]] = [
    ("❓解释概念", "explain"),
    ("💬追问", "discuss"),
]


# ---------------------------------------------------------------------------
# Card builder
# ---------------------------------------------------------------------------


def build_push_card(
    content: ContentResponseSchema,
) -> tuple[str, InlineKeyboardMarkup]:
    """Build Telegram push card text and inline keyboard markup.

    Returns (text, markup) — text is Markdown-formatted, markup has 6 buttons.
    """
    title = content.title or "(无标题)"
    summary = content.summary or ""
    read_time = content.estimated_read_time
    source_url = content.source_url

    lines: list[str] = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Header — read time if available
    if read_time:
        lines.append(f"📚 预计阅读 {read_time} 分钟")
    else:
        lines.append("📚 内容推送")

    lines.append("")
    lines.append(f"*{title}*")
    lines.append("")

    # Summary
    lines.append("┈┈ 核心内容 ┈┈")
    lines.append(summary)
    lines.append("")

    # Key points
    if content.key_points:
        lines.append("┈┈ 关键要点 ┈┈")
        for point in content.key_points:
            lines.append(f"• {point}")
        lines.append("")

    # Source link
    lines.append(f"🔗 [原文链接]({source_url})")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    text = "\n".join(lines)

    # Build inline keyboard — 2 rows of 3
    row1 = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"feedback:{fb_type}:{content.id}",
        )
        for label, fb_type in _FEEDBACK_BUTTONS[:3]
    ]
    row2_feedback = [
        InlineKeyboardButton(
            text=_FEEDBACK_BUTTONS[3][0],
            callback_data=f"feedback:{_FEEDBACK_BUTTONS[3][1]}:{content.id}",
        )
    ]
    row2_extra = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"{cb_prefix}:{content.id}",
        )
        for label, cb_prefix in _EXTRA_BUTTONS
    ]
    row2 = row2_feedback + row2_extra

    markup = InlineKeyboardMarkup(inline_keyboard=[row1, row2])
    return text, markup


# ---------------------------------------------------------------------------
# Send push
# ---------------------------------------------------------------------------


async def send_push(*, bot: Bot, chat_id: int, content: ContentResponseSchema) -> None:
    """Send a formatted push card to the given chat_id."""
    text, markup = build_push_card(content)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# In-memory token-bucket rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple in-memory token bucket rate limiter.

    Enforces:
    - per_user_rate: max messages per second per user
    - global_rate: max messages per second across all users
    """

    def __init__(self, per_user_rate: float = 1.0, global_rate: float = 30.0) -> None:
        self._per_user_rate = per_user_rate
        self._global_rate = global_rate
        # last send timestamp per user
        self._user_last: dict[int, float] = {}
        # tokens available globally (simple leaky bucket)
        self._global_tokens: float = global_rate
        self._global_last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def check(self, user_id: int) -> bool:
        """Return True if message is allowed, False if rate-limited."""
        async with self._lock:
            now = time.monotonic()

            # Refill global tokens
            elapsed = now - self._global_last_refill
            self._global_tokens = min(
                self._global_rate,
                self._global_tokens + elapsed * self._global_rate,
            )
            self._global_last_refill = now

            # Check global limit
            if self._global_tokens < 1.0:
                return False

            # Check per-user limit
            last = self._user_last.get(user_id, 0.0)
            min_interval = 1.0 / self._per_user_rate
            if (now - last) < min_interval:
                return False

            # Consume
            self._global_tokens -= 1.0
            self._user_last[user_id] = now
            return True


# Singleton rate limiter used by the bot
rate_limiter = RateLimiter(per_user_rate=1.0, global_rate=30.0)
