"""Unit tests for MatchingService — content-user matching algorithm."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from alice.graph.extractor import ContentSubgraph, ContentSubgraphEdge, ContentSubgraphNode
from alice.graph.user_kg import KnowledgeNode
from alice.services.matching import (
    DEFAULT_RECOMMEND_THRESHOLD,
    MASTERY_THRESHOLD,
    MAX_HOPS,
    MatchingService,
    MatchResult,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_subgraph(
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
    difficulty: float = 0.5,
    entry_concepts: list[str] | None = None,
) -> ContentSubgraph:
    """Build a ContentSubgraph for test scenarios."""
    n = [ContentSubgraphNode(name=d["name"], type=d.get("type", "concept")) for d in (nodes or [])]
    e = [
        ContentSubgraphEdge(
            **{"from": d["from"], "to": d["to"], "relation": d.get("relation", "extends")}
        )
        for d in (edges or [])
    ]
    return ContentSubgraph(
        nodes=n,
        edges=e,
        difficulty=difficulty,
        entry_concepts=entry_concepts or [],
    )


def _make_service(
    neo4j_rows: list[dict] | None = None,
    user_knowledge: list[KnowledgeNode] | None = None,
) -> tuple[MatchingService, MagicMock]:
    """Build MatchingService with mocked GraphClient + UserKnowledgeGraph."""
    client = MagicMock()
    client.execute_query = AsyncMock(return_value=neo4j_rows or [])
    svc = MatchingService(client)
    # Patch the UserKnowledgeGraph inside the service
    svc._user_kg = MagicMock()
    svc._user_kg.get_knowledge_map = AsyncMock(return_value=user_knowledge or [])
    svc._user_kg.get_knowledge_gaps = AsyncMock(return_value=[])
    return svc, client


# ---------------------------------------------------------------------------
# Tests — prerequisite coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prerequisite_coverage_all_known() -> None:
    """User knows all entry concepts → coverage = 1.0."""
    known = [KnowledgeNode(concept="transformers", mastery=0.8)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "transformers"}],
        entry_concepts=["transformers"],
        difficulty=0.5,
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.prerequisite_coverage == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_prerequisite_coverage_none_known() -> None:
    """User knows nothing → coverage = 0.0."""
    svc, _ = _make_service(user_knowledge=[])
    subgraph = _make_subgraph(
        nodes=[{"name": "quantum_computing"}],
        entry_concepts=["quantum_computing"],
        difficulty=0.9,
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.prerequisite_coverage == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_prerequisite_coverage_partial() -> None:
    """User knows 1 of 2 entry concepts → coverage = 0.5."""
    known = [KnowledgeNode(concept="attention", mastery=0.7)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "attention"}, {"name": "multi_head_attention"}],
        entry_concepts=["attention", "multi_head_attention"],
        difficulty=0.5,
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.prerequisite_coverage == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_prerequisite_below_mastery_threshold_not_counted() -> None:
    """Mastery of 0.2 is below threshold (0.3) → not counted as known."""
    known = [KnowledgeNode(concept="transformers", mastery=0.2)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(entry_concepts=["transformers"])
    result = await svc.compute_match_score(1, subgraph)
    assert result.prerequisite_coverage == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_empty_entry_concepts_returns_full_coverage() -> None:
    """No entry concepts → assume fully accessible → 1.0."""
    svc, _ = _make_service(user_knowledge=[])
    subgraph = _make_subgraph(nodes=[{"name": "some_advanced_topic"}], entry_concepts=[])
    result = await svc.compute_match_score(1, subgraph)
    assert result.prerequisite_coverage == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests — difficulty fit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_difficulty_fit_perfect_match() -> None:
    """Content difficulty matches user average mastery → fit = 1.0."""
    known = [KnowledgeNode(concept="ml", mastery=0.6)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(difficulty=0.6, entry_concepts=[])
    result = await svc.compute_match_score(1, subgraph)
    assert result.difficulty_fit == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_difficulty_fit_large_gap() -> None:
    """Beginner user (0.1 mastery) facing expert content (0.9 difficulty) → poor fit."""
    known = [KnowledgeNode(concept="basics", mastery=0.1)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(difficulty=0.9, entry_concepts=[])
    result = await svc.compute_match_score(1, subgraph)
    # fit = 1 - |0.9 - 0.1| = 0.2
    assert result.difficulty_fit == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_difficulty_fit_no_knowledge_defaults_to_half() -> None:
    """No knowledge → defaults user_avg=0.5, so difficulty_fit = 1-|d-0.5|."""
    svc, _ = _make_service(user_knowledge=[])
    subgraph = _make_subgraph(difficulty=0.5, entry_concepts=[])
    result = await svc.compute_match_score(1, subgraph)
    # user_avg = 0.5, difficulty = 0.5 → fit = 1.0
    assert result.difficulty_fit == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests — Match_score combined + threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_score_high_for_ready_user() -> None:
    """User has prerequisites and matching difficulty → high match score."""
    known = [
        KnowledgeNode(concept="transformers", mastery=0.8),
        KnowledgeNode(concept="attention", mastery=0.7),
    ]
    # Neo4j returns dist=1 for concept distance
    svc, client = _make_service(
        user_knowledge=known,
        neo4j_rows=[{"dist": 1}],
    )
    subgraph = _make_subgraph(
        nodes=[{"name": "multi_head_attention"}, {"name": "transformers"}],
        entry_concepts=["transformers", "attention"],
        difficulty=0.6,
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.match_score > 0.5
    assert result.should_defer is False


@pytest.mark.asyncio
async def test_match_score_low_for_total_beginner() -> None:
    """User knows nothing, advanced content → low score, should defer."""
    svc, _ = _make_service(
        user_knowledge=[],
        neo4j_rows=[],  # no path found
    )
    subgraph = _make_subgraph(
        nodes=[{"name": "quantum_entanglement"}, {"name": "bloch_sphere"}],
        entry_concepts=["quantum_mechanics", "linear_algebra"],
        difficulty=0.95,
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.match_score < DEFAULT_RECOMMEND_THRESHOLD
    assert result.should_defer is True


@pytest.mark.asyncio
async def test_match_score_clamped_to_0_1() -> None:
    """Match score is always in [0, 1]."""
    known = [KnowledgeNode(concept="x", mastery=1.0) for _ in range(5)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "x"}],
        entry_concepts=["x"],
        difficulty=1.0,
    )
    result = await svc.compute_match_score(1, subgraph)
    assert 0.0 <= result.match_score <= 1.0


# ---------------------------------------------------------------------------
# Tests — concept distance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concept_distance_fit_all_known() -> None:
    """User knows all content concepts → concept_distance_fit = 1.0."""
    known = [
        KnowledgeNode(concept="transformers", mastery=0.8),
        KnowledgeNode(concept="attention", mastery=0.7),
    ]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "transformers"}, {"name": "attention"}],
        entry_concepts=[],
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.concept_distance_fit == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_concept_distance_no_known_concepts() -> None:
    """User knows nothing → distance fit = 0.0."""
    svc, _ = _make_service(user_knowledge=[], neo4j_rows=[])
    subgraph = _make_subgraph(
        nodes=[{"name": "advanced_ml"}],
        entry_concepts=[],
    )
    result = await svc.compute_match_score(1, subgraph)
    assert result.concept_distance_fit == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_concept_distance_no_content_nodes() -> None:
    """Subgraph has no nodes → neutral distance = 0.5."""
    known = [KnowledgeNode(concept="ml", mastery=0.5)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(nodes=[], entry_concepts=[])
    result = await svc.compute_match_score(1, subgraph)
    assert result.concept_distance_fit == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_shortest_path_query_failure_treated_as_far() -> None:
    """If Neo4j query fails for shortest path, treat as distance = MAX_HOPS+1."""
    known = [KnowledgeNode(concept="ml", mastery=0.5)]
    client = MagicMock()
    client.execute_query = AsyncMock(side_effect=Exception("Neo4j down"))
    svc = MatchingService(client)
    svc._user_kg = MagicMock()
    svc._user_kg.get_knowledge_map = AsyncMock(return_value=known)
    subgraph = _make_subgraph(nodes=[{"name": "unknown_topic"}], entry_concepts=[])
    # Should not raise, just produce a low score
    result = await svc.compute_match_score(1, subgraph)
    assert result.concept_distance_fit < 0.5  # far away → low score


# ---------------------------------------------------------------------------
# Tests — R_relevance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r_relevance_returns_float_in_range() -> None:
    """compute_r_relevance always returns a value in [0, 1]."""
    known = [KnowledgeNode(concept="ml", mastery=0.6)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "ml"}],
        entry_concepts=["ml"],
        difficulty=0.6,
    )
    r = await svc.compute_r_relevance(1, subgraph)
    assert 0.0 <= r <= 1.0


@pytest.mark.asyncio
async def test_r_relevance_higher_for_ready_user() -> None:
    """User ready for content → R_relevance > user with no knowledge."""
    known_expert = [KnowledgeNode(concept="attention", mastery=0.9)]
    svc_expert, _ = _make_service(user_knowledge=known_expert)
    subgraph = _make_subgraph(
        nodes=[{"name": "attention"}],
        entry_concepts=["attention"],
        difficulty=0.5,
    )
    r_expert = await svc_expert.compute_r_relevance(1, subgraph)

    svc_novice, _ = _make_service(user_knowledge=[])
    r_novice = await svc_novice.compute_r_relevance(1, subgraph)

    assert r_expert > r_novice
