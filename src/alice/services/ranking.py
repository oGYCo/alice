"""Push priority ranking service — P_score formula."""

from __future__ import annotations

# pyright: reportMissingTypeStubs=false
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.content import Content, PipelineStatus

if TYPE_CHECKING:
    pass


class _Logger(Protocol):
    def info(self, event: str, **kwargs: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


class RankingService:
    """Computes P_score = Q * R * T * D * U + eps.

    Phase 2+ placeholders (T_timing=1.0, eps_explore=0.0) will be filled in
    when scheduling is implemented (Phase 3/4). R_relevance is now computed
    by MatchingService (T32) and passed in as a parameter.
    """

    # Half-lives for decay factor
    TIME_SENSITIVE_HALF_LIFE_HOURS: float = 24.0  # arxiv/news: 24h half-life
    KNOWLEDGE_HALF_LIFE_HOURS: float = 168.0  # evergreen: 7-day half-life
    DECAY_MINIMUM: float = 0.01  # never fully zero

    def compute_p_score(
        self,
        content: Content,
        now: datetime | None = None,
        r_relevance: float = 1.0,
        t_timing: float | None = None,
    ) -> float:
        """Compute P_score for a single content item.

        Formula: P_score = Q * R * T * D * U + eps

        Args:
            r_relevance: KG-based relevance score from MatchingService (T32).
                         Defaults to 1.0 when matching is not available.
            t_timing:    Schedule-window timing factor from PushScheduler.
                         Defaults to ``None`` which falls back to 1.0 for
                         backward compatibility.  Pass 0.0 during quiet hours
                         to suppress the item entirely.

        Returns a float clamped to [0.0, 2.0].
        """
        if now is None:
            now = datetime.now(UTC)

        q_content = self._compute_q_content(content)
        if t_timing is None:
            t_timing = 1.0
        d_decay = self._compute_d_decay(content, now)
        u_urgency = self._compute_u_urgency(content)
        epsilon_explore = 0.0  # Phase 4: eps-greedy

        p_score = q_content * r_relevance * t_timing * d_decay * u_urgency + epsilon_explore

        # Clamp to [0.0, 2.0]; U_urgency=1.5 can push above 1.0
        return max(0.0, min(2.0, p_score))

    def _compute_q_content(self, content: Content) -> float:
        """Normalize quality_score to [0.0, 1.0]. Default 0.5 if missing."""
        if content.quality_score is None:
            return 0.5
        # quality_score is 1-10 scale → normalize to 0.0-1.0
        return max(0.0, min(1.0, content.quality_score / 10.0))

    def _compute_d_decay(self, content: Content, now: datetime) -> float:
        """Exponential decay: D_decay = 0.5^(age_hours / half_life).

        Time-sensitive content (arxiv or "news"/"time_sensitive" in metadata_):
            half_life = 24 hours
        Knowledge content (default):
            half_life = 168 hours (7 days)

        Age reference: published_at if available, else created_at.
        Minimum: DECAY_MINIMUM (0.01) — never fully zero.
        """
        # Determine reference time for age calculation
        ref_time = cast(datetime | None, content.published_at or content.created_at)
        if ref_time is None:
            # No time info — treat as fresh
            return 1.0

        # Ensure timezone-aware comparison
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=UTC)

        age_seconds = (now - ref_time).total_seconds()
        age_hours = max(0.0, age_seconds / 3600.0)  # clamp negative ages to 0

        # Determine content type for half-life selection
        is_time_sensitive = self._is_time_sensitive(content)
        half_life = (
            self.TIME_SENSITIVE_HALF_LIFE_HOURS
            if is_time_sensitive
            else self.KNOWLEDGE_HALF_LIFE_HOURS
        )

        decay = math.pow(0.5, age_hours / half_life)
        return max(self.DECAY_MINIMUM, decay)

    def _is_time_sensitive(self, content: Content) -> bool:
        """Return True if content should use fast (24h) decay."""
        # arxiv papers are time-sensitive (new research)
        if content.source == "arxiv":
            return True
        # Check metadata for explicit content_type marker
        metadata = cast(dict[str, object], content.metadata_ or {})
        content_type = str(metadata.get("content_type", ""))
        return content_type in ("news", "time_sensitive")

    def _compute_u_urgency(self, content: Content) -> float:
        """Return 1.5 for high-urgency content, else 1.0.

        High urgency is set by connectors via metadata_["urgency"] = "high"
        (e.g., breaking news, imminent DDL).
        """
        metadata = cast(dict[str, object], content.metadata_ or {})
        if str(metadata.get("urgency", "")) == "high":
            return 1.5
        return 1.0

    async def update_p_score(
        self,
        session: AsyncSession,
        content: Content,
    ) -> float:
        """Compute and persist p_score on the content row. Returns the new score."""
        del session
        now = datetime.now(UTC)
        p_score = self.compute_p_score(content, now=now)
        content.p_score = p_score  # type: ignore[assignment]

        logger.info(
            "p_score_updated",
            content_id=content.id,
            p_score=round(p_score, 4),
            quality_score=content.quality_score,
        )
        return p_score

    async def batch_update_p_scores(
        self,
        session: AsyncSession,
        limit: int = 100,
    ) -> int:
        """Update p_score for up to `limit` indexed items. Returns count updated."""
        result = await session.execute(
            select(Content).where(Content.pipeline_status == PipelineStatus.indexed).limit(limit)
        )
        contents = list(result.scalars().all())

        now = datetime.now(UTC)
        for content in contents:
            content.p_score = self.compute_p_score(content, now=now)  # type: ignore[assignment]

        await session.commit()

        logger.info("batch_p_scores_updated", count=len(contents))
        return len(contents)
