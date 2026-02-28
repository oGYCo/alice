"""Telegram bot main entry point.

Runs as a standalone aiohttp application on port 8081 (webhook mode).
Separate from the FastAPI app — do NOT embed this in alice.main.

Usage:
    uv run python -m alice.bot.main
"""

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from alice.bot.handlers import commands
from alice.bot.handlers import feedback as feedback_handler
from alice.bot.handlers import review as review_handler
from alice.bot.handlers.commands import get_mode_name
from alice.bot.i18n import LanguageMiddleware, set_user_language, t
from alice.config import settings
from alice.services.user_state import UserMode, get_user_state_manager

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"
BOT_HOST = "0.0.0.0"
BOT_PORT = 8081


def create_app() -> web.Application:
    """Build and return the aiohttp application with bot webhook configured."""
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # Register command handlers
    dp.include_router(commands.router)

    # Register language middleware for all event types
    dp.message.middleware(LanguageMiddleware())
    dp.callback_query.middleware(LanguageMiddleware())

    # Register feedback callback handler (feedback:{type}:{id})
    @dp.callback_query(lambda q: q.data and q.data.startswith("feedback:"))
    async def _feedback_cb(query: CallbackQuery, lang: str = "zh") -> None:
        await feedback_handler.handle_feedback_callback(query, bot, lang=lang)

    # Register explain_concept placeholder (explain:{id})
    @dp.callback_query(lambda q: q.data and q.data.startswith("explain:"))
    async def _explain_cb(query: CallbackQuery, lang: str = "zh") -> None:
        await feedback_handler.handle_explain_concept(query, bot, lang=lang)

    # Register discuss placeholder (discuss:{id})
    @dp.callback_query(lambda q: q.data and q.data.startswith("discuss:"))
    async def _discuss_cb(query: CallbackQuery, lang: str = "zh") -> None:
        await feedback_handler.handle_discuss(query, bot, lang=lang)

    # Register review card rating callback (review:{card_id}:{rating})
    @dp.callback_query(lambda q: q.data and q.data.startswith("review:"))
    async def _review_cb(query: CallbackQuery, lang: str = "zh") -> None:
        await review_handler.handle_review_callback(query, bot, lang=lang)

    # Register language switch callback (lang:{code})
    @dp.callback_query(lambda q: q.data and q.data.startswith("lang:"))
    async def _lang_cb(query: CallbackQuery) -> None:
        parts = (query.data or "").split(":")
        if len(parts) != 2 or parts[1] not in ("zh", "en"):
            await query.answer(text=t("invalid_operation"))
            return
        target_lang = parts[1]
        await set_user_language(query.from_user.id, target_lang)
        await query.answer(text=t("lang_switched", target_lang))

    # Register mode switch callback (mode:{mode_value})
    @dp.callback_query(lambda q: q.data and q.data.startswith("mode:"))
    async def _mode_cb(query: CallbackQuery, lang: str = "zh") -> None:
        parts = (query.data or "").split(":")
        if len(parts) != 2:
            await query.answer(text=t("invalid_operation", lang))
            return
        try:
            target = UserMode(parts[1])
        except ValueError:
            await query.answer(text=t("invalid_mode", lang))
            return
        user_id = query.from_user.id
        mgr = get_user_state_manager()
        result = mgr.transition(user_id, target)
        name = get_mode_name(result.new_mode, lang)
        await query.answer(text=t("mode_switched", lang, name=name))

    # Build aiohttp app and register webhook handler
    app = web.Application()

    # Use secret_token for webhook signature verification when configured
    webhook_secret = settings.TELEGRAM_WEBHOOK_SECRET or None
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=webhook_secret
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Auto-register webhook with Telegram on startup when TELEGRAM_WEBHOOK_HOST is set
    async def _on_startup(_app: web.Application) -> None:
        webhook_host = settings.TELEGRAM_WEBHOOK_HOST.rstrip("/")
        if webhook_host:
            webhook_url = f"{webhook_host}{WEBHOOK_PATH}"
            webhook_kwargs: dict[str, object] = {"drop_pending_updates": False}
            if settings.TELEGRAM_WEBHOOK_SECRET:
                webhook_kwargs["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET
            await bot.set_webhook(webhook_url, **webhook_kwargs)  # type: ignore[arg-type]
            logger.info("Webhook registered: %s", webhook_url)
        else:
            logger.warning("TELEGRAM_WEBHOOK_HOST not set — webhook not registered")

    async def _on_shutdown(_app: web.Application) -> None:
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Webhook deleted on shutdown")

    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)

    # Health check endpoint for Docker healthcheck
    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", health)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    application = create_app()
    web.run_app(application, host=BOT_HOST, port=BOT_PORT)
