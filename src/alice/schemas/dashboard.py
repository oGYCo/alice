"""Dashboard response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeeklyVelocity(BaseModel):
    """Items read per week for velocity chart."""

    week: str = Field(description="ISO week label, e.g. '2026-W08'")
    count: int = Field(description="Number of items read/processed that week")


class KnowledgeGrowthPoint(BaseModel):
    """KG node counts over time."""

    week: str
    total_nodes: int
    new_nodes: int
    mastered_nodes: int = Field(description="Nodes with mastery >= 0.8")


class MemoryTierStats(BaseModel):
    """Count of items per memory tier."""

    working: int = 0
    short_term: int = 0
    long_term: int = 0


class CommunityInfo(BaseModel):
    """Simplified community cluster info for dashboard map."""

    community_id: int
    label: str
    concept_count: int
    avg_mastery: float
    top_concepts: list[str] = Field(default_factory=list, description="Top 5 concepts")


class ReviewScheduleStats(BaseModel):
    """FSRS review schedule summary."""

    due_today: int = 0
    due_this_week: int = 0
    total_cards: int = 0
    streak_days: int = 0
    cards_by_state: dict[str, int] = Field(default_factory=dict)


class ModeHistoryEntry(BaseModel):
    """A mode transition entry."""

    mode: str
    timestamp: str | None = None


class ModeInfo(BaseModel):
    """Current user mode and recent history."""

    current_mode: str = "daily"
    recent_history: list[ModeHistoryEntry] = Field(default_factory=list)


class DashboardStats(BaseModel):
    """Aggregated dashboard response model."""

    learning_velocity: list[WeeklyVelocity] = Field(default_factory=list)
    knowledge_growth: list[KnowledgeGrowthPoint] = Field(default_factory=list)
    memory_tiers: MemoryTierStats = Field(default_factory=MemoryTierStats)
    communities: list[CommunityInfo] = Field(default_factory=list)
    review_schedule: ReviewScheduleStats = Field(default_factory=ReviewScheduleStats)
    mode_info: ModeInfo = Field(default_factory=ModeInfo)
