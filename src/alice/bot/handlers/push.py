"""Push notification formatting and delivery with rate limiting."""

import asyncio
import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from alice.prompts import prompt_manager
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


def _get_card_type(content: ContentResponseSchema) -> str:
    """Infer card type from content metadata classification."""
    metadata = content.metadata_ or {}
    content_type = metadata.get("content_type", "deep_knowledge")
    if content_type in ("time_sensitive", "news", "release"):
        return "time_sensitive"
    if content_type in ("thought_provoking", "opinion", "essay"):
        return "thought_provoking"
    return "deep_knowledge"  # default


def _build_buttons_for_card_type(
    card_type: str, content_id: int
) -> list[list[InlineKeyboardButton]]:
    """Build inline keyboard based on card type."""
    if card_type == "time_sensitive":
        # 1 row, 2 buttons
        row = [
            InlineKeyboardButton(
                text="✅已了解",
                callback_data=f"feedback:valuable_learned:{content_id}",
            ),
            InlineKeyboardButton(
                text="📌需要跟进",
                callback_data=f"feedback:save_for_later:{content_id}",
            ),
        ]
        return [row]
    elif card_type == "thought_provoking":
        # 1 row, 4 buttons
        row = [
            InlineKeyboardButton(
                text="👍有启发",
                callback_data=f"feedback:valuable_learned:{content_id}",
            ),
            InlineKeyboardButton(
                text="⏰稍后",
                callback_data=f"feedback:save_for_later:{content_id}",
            ),
            InlineKeyboardButton(
                text="👎无感",
                callback_data=f"feedback:not_valuable:{content_id}",
            ),
            InlineKeyboardButton(
                text="💬讨论",
                callback_data=f"discuss:{content_id}",
            ),
        ]
        return [row]
    else:
        # deep_knowledge: 2 rows, 3+3 buttons
        row1 = [
            InlineKeyboardButton(
                text=label,
                callback_data=f"feedback:{fb_type}:{content_id}",
            )
            for label, fb_type in _FEEDBACK_BUTTONS[:3]
        ]
        row2_feedback = [
            InlineKeyboardButton(
                text=_FEEDBACK_BUTTONS[3][0],
                callback_data=f"feedback:{_FEEDBACK_BUTTONS[3][1]}:{content_id}",
            )
        ]
        row2_extra = [
            InlineKeyboardButton(
                text=label,
                callback_data=f"{cb_prefix}:{content_id}",
            )
            for label, cb_prefix in _EXTRA_BUTTONS
        ]
        row2 = row2_feedback + row2_extra
        return [row1, row2]


def build_push_card(
    content: ContentResponseSchema,
) -> tuple[str, InlineKeyboardMarkup]:
    """Build Telegram push card text and inline keyboard markup using PromptManager.

    Returns (text, markup) — text is Markdown-formatted, markup has buttons based on card type.
    """
    card_type = _get_card_type(content)
    metadata = content.metadata_ or {}

    text = prompt_manager.render(
        "push_card",
        card_type=card_type,
        title=content.title or "(无标题)",
        summary=content.summary or "",
        key_points=content.key_points or [],
        source_url=content.source_url or "",
        estimated_read_time=content.estimated_read_time,
        push_reason=metadata.get("push_reason", ""),
        reading_advice=metadata.get("reading_advice", ""),
        what=metadata.get("what", ""),
        impact=metadata.get("impact", ""),
    )

    # Build inline keyboard based on card type
    keyboard = _build_buttons_for_card_type(card_type, content.id)
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
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
