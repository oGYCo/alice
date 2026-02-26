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
from alice.config import settings

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

    # Register feedback callback handler (feedback:{type}:{id})
    @dp.callback_query(lambda q: q.data and q.data.startswith("feedback:"))
    async def _feedback_cb(query: CallbackQuery) -> None:
        await feedback_handler.handle_feedback_callback(query, bot)

    # Register explain_concept placeholder (explain:{id})
    @dp.callback_query(lambda q: q.data and q.data.startswith("explain:"))
    async def _explain_cb(query: CallbackQuery) -> None:
        await feedback_handler.handle_explain_concept(query, bot)

    # Register discuss placeholder (discuss:{id})
    @dp.callback_query(lambda q: q.data and q.data.startswith("discuss:"))
    async def _discuss_cb(query: CallbackQuery) -> None:
        await feedback_handler.handle_discuss(query, bot)

    # Build aiohttp app and register webhook handler
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Health check endpoint for Docker healthcheck
    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", health)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    application = create_app()
    web.run_app(application, host=BOT_HOST, port=BOT_PORT)
