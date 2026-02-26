"""Push service — fetch indexed content, format cards, deliver via Telegram bot."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.bot.handlers.push import send_push
from alice.models.content import Content, PipelineStatus
from alice.prompts import PromptManager
from alice.prompts import prompt_manager as _default_pm
from alice.schemas.content import ContentResponseSchema


class PushService:
    """Service for fetching, formatting, and delivering pushed content."""

    def __init__(self, pm: PromptManager | None = None) -> None:
        self._pm = pm or _default_pm

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_next_push_batch(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 5,
    ) -> list[Content]:
        """Return up to `limit` indexed, unpushed content items ordered by quality_score DESC.

        Selects content where:
        - pipeline_status == 'indexed'
        - pushed_at is NULL (not yet delivered)

        Ordered by quality_score DESC so highest-quality content is delivered first.
        """
        result = await session.execute(
            select(Content)
            .where(
                Content.pipeline_status == PipelineStatus.indexed,
                Content.pushed_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(Content.p_score.desc().nullslast(), Content.quality_score.desc())  # type: ignore[union-attr]
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_push_card(self, content: Content) -> str:
        """Render the push_card.j2 Jinja2 template for the given content.

        Returns a Markdown-formatted string suitable for Telegram.
        """
        return self._pm.render(
            "push_card",
            title=content.title,
            summary=content.summary,
            key_points=content.key_points,
            source_url=content.source_url,
            estimated_read_time=content.estimated_read_time,
        )

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    async def deliver_push(
        self,
        *,
        bot: Bot,
        user_id: int,
        chat_id: int,
        content_list: list[Content],
        session: AsyncSession,
    ) -> None:
        """Deliver push cards to a Telegram user and record timestamps.

        For each content item:
        1. Build a ContentResponseSchema (required by send_push)
        2. Call send_push() to deliver the card
        3. Set content.pushed_at = now(UTC) to mark as delivered

        Commits once after all deliveries.
        """
        if not content_list:
            return

        now = datetime.now(UTC)

        for content in content_list:
            schema = ContentResponseSchema.model_validate(content)
            await send_push(bot=bot, chat_id=chat_id, content=schema)
            content.pushed_at = now

        await session.commit()
