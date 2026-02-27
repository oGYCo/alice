"""Knowledge Graph API schemas for interactive visualization."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KGNodeOut(BaseModel):
    """A concept node for the KG visualization API."""

    id: str = Field(description="Unique node identifier (concept name)")
    name: str = Field(description="Display name of the concept")
    label: str = Field(default="Concept", description="Node type: Concept, Method, Tool, Theory")
    mastery: float = Field(default=0.0, ge=0.0, le=1.0, description="User mastery level 0-1")
    community_id: int | None = Field(default=None, description="Community cluster ID")
    aliases: list[str] = Field(default_factory=list)


class KGEdgeOut(BaseModel):
    """A relationship edge for the KG visualization API."""

    id: str = Field(description="Unique edge identifier")
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    label: str = Field(description="Relationship type")


class KGGraphOut(BaseModel):
    """Full graph response in React Flow compatible format."""

    nodes: list[KGNodeOut] = Field(default_factory=list)
    edges: list[KGEdgeOut] = Field(default_factory=list)
    total_nodes: int = Field(default=0)
    total_edges: int = Field(default=0)


class KGCommunityOut(BaseModel):
    """Community cluster info for filtering."""

    community_id: int
    label: str
    concept_count: int
    avg_mastery: float
    concepts: list[str] = Field(default_factory=list)


class KGGapSuggestion(BaseModel):
    """A suggested concept to learn next based on graph neighborhood."""

    concept: str
    mastery: float
    adjacent_mastered: list[str] = Field(
        default_factory=list,
        description="Mastered concepts adjacent to this gap"
    )
    reason: str = ""


class KGGapAnalysis(BaseModel):
    """Knowledge gap analysis result."""

    gaps: list[KGGapSuggestion] = Field(default_factory=list)
    total_gaps: int = 0


class KGNodeUpdateIn(BaseModel):
    """Request body for updating a KG node."""

    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    name: str | None = Field(default=None, min_length=1, max_length=200)


class KGEdgeCreateIn(BaseModel):
    """Request body for creating a KG edge."""

    source: str = Field(description="Source concept name")
    target: str = Field(description="Target concept name")
    relation: str = Field(description="Relationship type", pattern="^[A-Z_]+$")


class KGEdgeOut2(BaseModel):
    """Response for edge CRUD operations."""

    id: str
    source: str
    target: str
    relation: str
    created: bool = False
