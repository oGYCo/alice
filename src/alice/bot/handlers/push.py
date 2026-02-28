"""Push notification formatting and delivery with rate limiting."""

import asyncio
import logging
import re
import time

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from alice.bot.i18n import t
from alice.prompts import prompt_manager
from alice.schemas.content import ContentResponseSchema
from alice.schemas.feedback import FeedbackType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Markdown escaping
# ---------------------------------------------------------------------------

_MD_SPECIAL_RE = re.compile(r"([_*`\[\]])")


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown v1 special characters."""
    if not text:
        return text
    return _MD_SPECIAL_RE.sub(r"\\\1", text)


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
    card_type: str, content_id: int, lang: str = "zh",
) -> list[list[InlineKeyboardButton]]:
    """Build inline keyboard based on card type."""
    if card_type == "time_sensitive":
        row = [
            InlineKeyboardButton(
                text=t("btn_acknowledged", lang),
                callback_data=f"feedback:valuable_learned:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_follow_up", lang),
                callback_data=f"feedback:save_for_later:{content_id}",
            ),
        ]
        return [row]
    elif card_type == "thought_provoking":
        row = [
            InlineKeyboardButton(
                text=t("btn_inspiring", lang),
                callback_data=f"feedback:valuable_learned:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_later_short", lang),
                callback_data=f"feedback:save_for_later:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_meh", lang),
                callback_data=f"feedback:not_valuable:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_discuss_short", lang),
                callback_data=f"discuss:{content_id}",
            ),
        ]
        return [row]
    else:
        # deep_knowledge: 2 rows
        row1 = [
            InlineKeyboardButton(
                text=t("btn_quality", lang),
                callback_data=f"feedback:{FeedbackType.valuable_learned}:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_later", lang),
                callback_data=f"feedback:{FeedbackType.save_for_later}:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_known", lang),
                callback_data=f"feedback:{FeedbackType.already_known}:{content_id}",
            ),
        ]
        row2 = [
            InlineKeyboardButton(
                text=t("btn_not_valuable", lang),
                callback_data=f"feedback:{FeedbackType.not_valuable}:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_explain", lang),
                callback_data=f"explain:{content_id}",
            ),
            InlineKeyboardButton(
                text=t("btn_discuss", lang),
                callback_data=f"discuss:{content_id}",
            ),
        ]
        return [row1, row2]


def build_push_card(
    content: ContentResponseSchema,
    lang: str = "zh",
) -> tuple[str, InlineKeyboardMarkup]:
    """Build Telegram push card text and inline keyboard markup using PromptManager.

    Returns (text, markup) — text is Markdown-formatted, markup has buttons based on card type.
    """
    card_type = _get_card_type(content)
    metadata = content.metadata_ or {}

    template_name = "push_card" if lang == "zh" else "push_card_en"
    text = prompt_manager.render(
        template_name,
        card_type=card_type,
        title=_escape_markdown(content.title or "(无标题)"),
        summary=_escape_markdown(content.summary or ""),
        key_points=[_escape_markdown(p) for p in (content.key_points or [])],
        source_url=content.source_url or "",
        estimated_read_time=content.estimated_read_time,
        push_reason=_escape_markdown(metadata.get("push_reason", "")),
        reading_advice=_escape_markdown(metadata.get("reading_advice", "")),
        what=_escape_markdown(metadata.get("what", "")),
        impact=_escape_markdown(metadata.get("impact", "")),
    )

    # Build inline keyboard based on card type
    keyboard = _build_buttons_for_card_type(card_type, content.id, lang)
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return text, markup


# ---------------------------------------------------------------------------
# Send push
# ---------------------------------------------------------------------------


async def send_push(*, bot: Bot, chat_id: int, content: ContentResponseSchema, lang: str = "zh") -> None:
    """Send a formatted push card to the given chat_id.

    Attempts Markdown first; on ``TelegramBadRequest`` (typically caused by
    un-parseable markup) falls back to sending plain text so the delivery is
    not lost.
    """
    text, markup = build_push_card(content, lang=lang)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            parse_mode="Markdown",
        )
    except TelegramBadRequest:
        logger.warning(
            "send_push_markdown_fallback",
            extra={"chat_id": chat_id, "content_id": content.id},
        )
        # Retry without parse_mode so the user still receives the card
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
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
