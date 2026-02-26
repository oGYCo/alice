"""3-tier memory system: Working / Short-term / Long-term."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.user_memory import MemoryLayer, UserMemory


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

_SHORT_TERM_DECAY_DAYS = 14
_WORKING_MEMORY_PATTERN_THRESHOLD = 3
_WORKING_MEMORY_PATTERN_WINDOW_HOURS = 48
_WORKING_WEIGHT_BOOST = 3.0
_DECAY_FACTOR = 0.5


@dataclass
class MemoryContext:
    """Unified memory context for push scoring and ranking."""

    working_topics: list[str] = field(default_factory=list)
    short_term_topics: list[str] = field(default_factory=list)
    long_term_topics: list[str] = field(default_factory=list)
    working_weight_boost: float = 1.0


class MemoryManager:
    """Manages 3-tier memory per user. All methods require an AsyncSession."""

    def __init__(self) -> None:
        pass

    async def update_working_memory(
        self,
        session: AsyncSession,
        user_id: int,
        declaration: str | None = None,
        auto_infer: bool = False,
    ) -> UserMemory | None:
        """Set working memory from user declaration or auto-inference.

        Declaration sets a single working memory item (replacing any existing
        working memory for the same topic). Auto-infer requires a pattern of
        3+ related readings in 48h (checked externally; pass auto_infer=True
        only when pattern already confirmed).
        """
        if declaration is None and not auto_infer:
            return None

        topic = declaration or "auto_inferred"
        now = datetime.now(UTC)

        existing = await session.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.layer == MemoryLayer.working,
                UserMemory.topic == topic,
            )
        )
        row = existing.scalar_one_or_none()

        if row is not None:
            row.last_touched = now  # type: ignore[assignment]
            row.weight = _WORKING_WEIGHT_BOOST  # type: ignore[assignment]
            await session.commit()
            return row

        memory = UserMemory(
            user_id=user_id,
            layer=MemoryLayer.working,
            topic=topic,
            content=declaration or "auto_inferred",
            weight=_WORKING_WEIGHT_BOOST,
            last_touched=now,
        )
        session.add(memory)
        await session.commit()
        await session.refresh(memory)

        logger.info("working_memory_updated", user_id=user_id, topic=topic)
        return memory

    async def update_short_term(
        self,
        session: AsyncSession,
        user_id: int,
        topic: str,
        content: str = "",
    ) -> UserMemory:
        """Upsert a short-term memory item and reset last_touched."""
        now = datetime.now(UTC)

        existing = await session.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.layer == MemoryLayer.short_term,
                UserMemory.topic == topic,
            )
        )
        row = existing.scalar_one_or_none()

        if row is not None:
            row.last_touched = now  # type: ignore[assignment]
            row.weight = min(float(row.weight) + 0.1, 2.0)  # type: ignore[assignment]
            await session.commit()
            return row

        memory = UserMemory(
            user_id=user_id,
            layer=MemoryLayer.short_term,
            topic=topic,
            content=content or topic,
            weight=1.0,
            last_touched=now,
        )
        session.add(memory)
        await session.commit()
        await session.refresh(memory)
        return memory

    async def promote_to_long_term(
        self,
        session: AsyncSession,
        user_id: int,
        concept_id: str,
    ) -> UserMemory:
        """Promote a concept to long-term memory (mastery stable > 30 days)."""
        now = datetime.now(UTC)

        existing = await session.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.layer == MemoryLayer.long_term,
                UserMemory.topic == concept_id,
            )
        )
        row = existing.scalar_one_or_none()

        if row is not None:
            row.last_touched = now  # type: ignore[assignment]
            await session.commit()
            return row

        memory = UserMemory(
            user_id=user_id,
            layer=MemoryLayer.long_term,
            topic=concept_id,
            content=concept_id,
            weight=1.0,
            last_touched=now,
        )
        session.add(memory)
        await session.commit()
        await session.refresh(memory)
        logger.info("concept_promoted_to_long_term", user_id=user_id, concept_id=concept_id)
        return memory

    async def get_memory_context(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> MemoryContext:
        """Return unified memory context for ranking/scoring."""
        result = await session.execute(select(UserMemory).where(UserMemory.user_id == user_id))
        memories = list(result.scalars().all())

        working = [m.topic for m in memories if m.layer == MemoryLayer.working]
        short_term = [m.topic for m in memories if m.layer == MemoryLayer.short_term]
        long_term = [m.topic for m in memories if m.layer == MemoryLayer.long_term]

        boost = _WORKING_WEIGHT_BOOST if working else 1.0

        return MemoryContext(
            working_topics=working,
            short_term_topics=short_term,
            long_term_topics=long_term,
            working_weight_boost=boost,
        )

    async def decay_short_term(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> int:
        """Decay short-term items older than 14 days. Returns items removed."""
        cutoff = datetime.now(UTC) - timedelta(days=_SHORT_TERM_DECAY_DAYS)

        result = await session.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.layer == MemoryLayer.short_term,
                UserMemory.last_touched < cutoff,
            )
        )
        old_items = list(result.scalars().all())

        if not old_items:
            return 0

        for item in old_items:
            new_weight = float(item.weight) * _DECAY_FACTOR
            if new_weight < 0.1:
                await session.delete(item)
            else:
                item.weight = new_weight  # type: ignore[assignment]

        await session.commit()
        logger.info(
            "short_term_decayed",
            user_id=user_id,
            items_processed=len(old_items),
        )
        return len(old_items)

    async def archive_working_memory(
        self,
        session: AsyncSession,
        user_id: int,
        topic: str,
    ) -> int:
        """Archive (delete) a working memory item when project/task completes."""
        result = await session.execute(
            delete(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.layer == MemoryLayer.working,
                UserMemory.topic == topic,
            )
        )
        await session.commit()
        deleted = result.rowcount
        logger.info("working_memory_archived", user_id=user_id, topic=topic, deleted=deleted)
        return deleted

    @staticmethod
    def extract_topics_from_declaration(declaration: str) -> list[str]:
        """Extract candidate topic keywords from a free-text declaration."""
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9_\-]{2,}\b", declaration)
        seen: set[str] = set()
        topics = []
        for w in words:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                topics.append(w)
        return topics
