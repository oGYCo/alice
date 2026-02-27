"""Dashboard API router — GET /dashboard/stats."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.config import settings
from alice.db import get_db
from alice.models.content import Content, PipelineStatus
from alice.models.review_card import ReviewCard
from alice.models.user_memory import MemoryLayer, UserMemory
from alice.schemas.dashboard import (
    CommunityInfo,
    DashboardStats,
    KnowledgeGrowthPoint,
    MemoryTierStats,
    ModeHistoryEntry,
    ModeInfo,
    ReviewScheduleStats,
    WeeklyVelocity,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _learning_velocity(session: AsyncSession, user_id: int, weeks: int = 8) -> list[WeeklyVelocity]:
    """Compute items processed per week for the last N weeks."""
    now = datetime.now(UTC)
    result: list[WeeklyVelocity] = []

    for i in range(weeks - 1, -1, -1):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        iso_cal = week_end.isocalendar()
        week_label = f"{iso_cal.year}-W{iso_cal.week:02d}"

        stmt = (
            select(func.count())
            .select_from(Content)
            .where(
                Content.created_at >= week_start,
                Content.created_at < week_end,
                Content.pipeline_status.in_([
                    PipelineStatus.understood,
                    PipelineStatus.scored,
                    PipelineStatus.indexed,
                ]),
            )
        )
        if user_id:
            stmt = stmt.where(Content.user_id == user_id)

        row = await session.execute(stmt)
        count = row.scalar() or 0
        result.append(WeeklyVelocity(week=week_label, count=count))

    return result


async def _knowledge_growth(session: AsyncSession, user_id: int, weeks: int = 8) -> list[KnowledgeGrowthPoint]:
    """Compute KG-like growth metrics from content over time.

    Uses content domains as a proxy for knowledge nodes when Neo4j is unavailable.
    When Neo4j is available, enriches with real graph data.
    """
    now = datetime.now(UTC)
    result: list[KnowledgeGrowthPoint] = []
    cumulative_domains: set[str] = set()

    for i in range(weeks - 1, -1, -1):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        iso_cal = week_end.isocalendar()
        week_label = f"{iso_cal.year}-W{iso_cal.week:02d}"

        # Fetch content with domains for this week
        stmt = (
            select(Content.domains)
            .where(
                Content.created_at >= week_start,
                Content.created_at < week_end,
                Content.domains.isnot(None),
                Content.pipeline_status.in_([
                    PipelineStatus.understood,
                    PipelineStatus.scored,
                    PipelineStatus.indexed,
                ]),
            )
        )
        if user_id:
            stmt = stmt.where(Content.user_id == user_id)

        rows = await session.execute(stmt)
        week_domains: set[str] = set()
        for (domains,) in rows:
            if isinstance(domains, list):
                week_domains.update(d.lower() for d in domains if isinstance(d, str))

        new_nodes = len(week_domains - cumulative_domains)
        cumulative_domains.update(week_domains)

        # Count mastered (long-term memory topics) as mastered nodes
        mastered_stmt = (
            select(func.count())
            .select_from(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.layer == MemoryLayer.long_term,
            )
        )
        mastered_row = await session.execute(mastered_stmt)
        mastered = mastered_row.scalar() or 0

        result.append(KnowledgeGrowthPoint(
            week=week_label,
            total_nodes=len(cumulative_domains),
            new_nodes=new_nodes,
            mastered_nodes=mastered,
        ))

    return result


async def _memory_tiers(session: AsyncSession, user_id: int) -> MemoryTierStats:
    """Count memories per tier."""
    stmt = (
        select(UserMemory.layer, func.count())
        .where(UserMemory.user_id == user_id)
        .group_by(UserMemory.layer)
    )
    rows = await session.execute(stmt)
    counts: dict[str, int] = {}
    for layer, count in rows:
        counts[str(layer)] = count

    return MemoryTierStats(
        working=counts.get("working", 0),
        short_term=counts.get("short_term", 0),
        long_term=counts.get("long_term", 0),
    )


async def _communities(user_id: int) -> list[CommunityInfo]:
    """Get community data from Neo4j via CommunityDetector (best-effort)."""
    try:
        from alice.graph.client import GraphClient
        from alice.services.community_detection import CommunityDetector

        user, password = settings.NEO4J_AUTH.split("/", 1)
        async with GraphClient(settings.NEO4J_URI, (user, password)) as graph_client:
            detector = CommunityDetector(graph_client)
            raw_communities = await detector.detect_communities(user_id)
            return [
                CommunityInfo(
                    community_id=c.community_id,
                    label=c.label,
                    concept_count=len(c.concepts),
                    avg_mastery=c.avg_mastery,
                    top_concepts=c.concepts[:5],
                )
                for c in raw_communities
            ]
    except Exception:
        logger.warning("community_detection_unavailable", user_id=user_id)
        return []


async def _review_schedule(session: AsyncSession, user_id: int) -> ReviewScheduleStats:
    """Compute FSRS review schedule stats."""
    now = datetime.now(UTC)
    end_of_week = now + timedelta(days=7)

    # Total cards
    total_stmt = (
        select(func.count())
        .select_from(ReviewCard)
        .where(ReviewCard.user_id == user_id)
    )
    total = (await session.execute(total_stmt)).scalar() or 0

    # Due today
    due_today_stmt = (
        select(func.count())
        .select_from(ReviewCard)
        .where(
            ReviewCard.user_id == user_id,
            ReviewCard.due_date <= now,
        )
    )
    due_today = (await session.execute(due_today_stmt)).scalar() or 0

    # Due this week
    due_week_stmt = (
        select(func.count())
        .select_from(ReviewCard)
        .where(
            ReviewCard.user_id == user_id,
            ReviewCard.due_date <= end_of_week,
        )
    )
    due_week = (await session.execute(due_week_stmt)).scalar() or 0

    # Cards by state
    state_stmt = (
        select(ReviewCard.state, func.count())
        .where(ReviewCard.user_id == user_id)
        .group_by(ReviewCard.state)
    )
    state_rows = await session.execute(state_stmt)
    cards_by_state = {str(state): count for state, count in state_rows}

    # Streak: count consecutive days with at least one review (using updated_at)
    streak = 0
    check_date = now.date()
    for _ in range(365):
        day_start = datetime(check_date.year, check_date.month, check_date.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        day_count_stmt = (
            select(func.count())
            .select_from(ReviewCard)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.updated_at >= day_start,
                ReviewCard.updated_at < day_end,
                ReviewCard.reps > 0,
            )
        )
        day_count = (await session.execute(day_count_stmt)).scalar() or 0
        if day_count > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return ReviewScheduleStats(
        due_today=due_today,
        due_this_week=due_week,
        total_cards=total,
        streak_days=streak,
        cards_by_state=cards_by_state,
    )


def _mode_info(user_id: int) -> ModeInfo:
    """Get current user mode and history from in-memory state manager."""
    from alice.services.user_state import UserStateManager

    mgr = UserStateManager()
    current = mgr.get_state(user_id)

    return ModeInfo(
        current_mode=str(current),
        recent_history=[ModeHistoryEntry(mode=str(current))],
    )


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: Annotated[int, Query(ge=1, description="User ID")] = 1,
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Aggregated dashboard stats for the cognitive dashboard.

    Returns learning velocity, knowledge growth, memory tiers,
    community map, review schedule, and mode info.
    """
    try:
        velocity = await _learning_velocity(session, user_id)
        growth = await _knowledge_growth(session, user_id)
        memory = await _memory_tiers(session, user_id)
        communities = await _communities(user_id)
        review = await _review_schedule(session, user_id)
        mode = _mode_info(user_id)

        return DashboardStats(
            learning_velocity=velocity,
            knowledge_growth=growth,
            memory_tiers=memory,
            communities=communities,
            review_schedule=review,
            mode_info=mode,
        )
    except Exception as exc:
        logger.error("dashboard_stats_error", error=str(exc), user_id=user_id)
        raise HTTPException(status_code=500, detail="Failed to load dashboard stats")
