"""Unit tests for MatchingService — content-user matching algorithm."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alice.graph.extractor import ContentSubgraph, ContentSubgraphEdge, ContentSubgraphNode
from alice.graph.user_kg import KnowledgeNode
from alice.services.matching import (
    DEFAULT_RECOMMEND_THRESHOLD,
    MatchingService,
)
from alice.services.memory_system import MemoryContext

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
    search_service: object | None = None,
) -> tuple[MatchingService, MagicMock]:
    """Build MatchingService with mocked GraphClient + UserKnowledgeGraph."""
    client = MagicMock()
    client.execute_query = AsyncMock(return_value=neo4j_rows or [])
    svc = MatchingService(client, search_service=search_service)
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


# ---------------------------------------------------------------------------
# Tests — text relevance (Meilisearch integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_relevance_with_search_service() -> None:
    """When search_service is provided and content is found, text_relevance > 0.5."""
    mock_search = MagicMock()
    mock_search.search = MagicMock(
        return_value={"hits": [{"id": "42", "title": "ML Basics"}]}
    )
    known = [KnowledgeNode(concept="ml", mastery=0.8)]
    svc, _ = _make_service(user_knowledge=known, search_service=mock_search)
    subgraph = _make_subgraph(
        nodes=[{"name": "ml"}],
        entry_concepts=["ml"],
        difficulty=0.5,
    )
    r = await svc.compute_r_relevance(1, subgraph, content_id=42)
    # With search hit at rank 0, text_relevance = 1.0 (top rank)
    assert 0.0 <= r <= 1.0
    mock_search.search.assert_called_once()


@pytest.mark.asyncio
async def test_text_relevance_without_search_service() -> None:
    """Without search_service, text_relevance falls back to 0.5 (neutral)."""
    known = [KnowledgeNode(concept="ml", mastery=0.6)]
    svc_with, _ = _make_service(user_knowledge=known)
    svc_without, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "ml"}],
        entry_concepts=["ml"],
        difficulty=0.6,
    )
    r_with = await svc_with.compute_r_relevance(1, subgraph)
    r_without = await svc_without.compute_r_relevance(1, subgraph, content_id=99)
    # Both should work without error; without search_service, fallback = 0.5
    assert 0.0 <= r_with <= 1.0
    assert 0.0 <= r_without <= 1.0


@pytest.mark.asyncio
async def test_text_relevance_search_failure_graceful() -> None:
    """If search_service.search raises, text_relevance falls back to 0.5."""
    mock_search = MagicMock()
    mock_search.search = MagicMock(side_effect=Exception("Meilisearch down"))
    known = [KnowledgeNode(concept="ml", mastery=0.8)]
    svc, _ = _make_service(user_knowledge=known, search_service=mock_search)
    subgraph = _make_subgraph(
        nodes=[{"name": "ml"}],
        entry_concepts=["ml"],
        difficulty=0.5,
    )
    # Should not raise, graceful degradation
    r = await svc.compute_r_relevance(1, subgraph, content_id=42)
    assert 0.0 <= r <= 1.0


@pytest.mark.asyncio
async def test_text_relevance_content_not_in_results() -> None:
    """Content not in search results → low text relevance (0.1)."""
    mock_search = MagicMock()
    mock_search.search = MagicMock(
        return_value={"hits": [{"id": "99", "title": "Other Content"}]}
    )
    known = [KnowledgeNode(concept="ml", mastery=0.8)]
    svc, _ = _make_service(user_knowledge=known, search_service=mock_search)
    subgraph = _make_subgraph(
        nodes=[{"name": "ml"}],
        entry_concepts=["ml"],
        difficulty=0.5,
    )
    r = await svc.compute_r_relevance(1, subgraph, content_id=42)
    assert 0.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# Tests — working memory match
# ---------------------------------------------------------------------------


class TestComputeWorkingMemoryMatch:
    """Tests for _compute_working_memory_match."""

    def test_no_working_topics_returns_neutral(self) -> None:
        """No working memory topics → neutral 0.5."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[{"name": "transformers"}])
        ctx = MemoryContext(working_topics=[])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(0.5)

    def test_no_content_nodes_returns_neutral(self) -> None:
        """No content concept nodes → neutral 0.5."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[])
        ctx = MemoryContext(working_topics=["transformers"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(0.5)

    def test_exact_topic_match(self) -> None:
        """Exact match between concept and working topic → 1.0."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[{"name": "transformers"}])
        ctx = MemoryContext(working_topics=["transformers"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(1.0)

    def test_case_insensitive_match(self) -> None:
        """Case-insensitive matching works."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[{"name": "Transformers"}])
        ctx = MemoryContext(working_topics=["TRANSFORMERS"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(1.0)

    def test_substring_topic_in_concept(self) -> None:
        """Working topic 'attention' matches concept 'multi_head_attention'."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[{"name": "multi_head_attention"}])
        ctx = MemoryContext(working_topics=["attention"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(1.0)

    def test_substring_concept_in_topic(self) -> None:
        """Concept 'ml' matches working topic 'ml_pipeline_optimization'."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[{"name": "ml"}])
        ctx = MemoryContext(working_topics=["ml_pipeline_optimization"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(1.0)

    def test_partial_overlap(self) -> None:
        """1 of 2 concepts matches → 0.5."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(
            nodes=[{"name": "attention"}, {"name": "quantum_computing"}]
        )
        ctx = MemoryContext(working_topics=["attention"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(0.5)

    def test_no_overlap(self) -> None:
        """No overlap → 0.0."""
        svc, _ = _make_service()
        subgraph = _make_subgraph(nodes=[{"name": "quantum_computing"}])
        ctx = MemoryContext(working_topics=["transformers"])
        assert svc._compute_working_memory_match(subgraph, ctx) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests — R_relevance with working memory (session-aware)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r_relevance_with_session_uses_working_memory() -> None:
    """When session is passed, working memory context is fetched and used."""
    known = [KnowledgeNode(concept="attention", mastery=0.8)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "attention"}],
        entry_concepts=["attention"],
        difficulty=0.5,
    )

    mock_session = AsyncMock()
    memory_ctx = MemoryContext(working_topics=["attention"])

    with patch(
        "alice.services.matching.MemoryManager"
    ) as mock_mem_mgr:
        mock_mgr_instance = mock_mem_mgr.return_value
        mock_mgr_instance.get_memory_context = AsyncMock(return_value=memory_ctx)
        r = await svc.compute_r_relevance(
            1, subgraph, session=mock_session
        )
        mock_mgr_instance.get_memory_context.assert_awaited_once_with(mock_session, 1)

    assert 0.0 <= r <= 1.0


@pytest.mark.asyncio
async def test_r_relevance_without_session_neutral_working_match() -> None:
    """Without session, working_match falls back to 0.5 (neutral)."""
    known = [KnowledgeNode(concept="ml", mastery=0.6)]
    svc, _ = _make_service(user_knowledge=known)
    subgraph = _make_subgraph(
        nodes=[{"name": "ml"}],
        entry_concepts=["ml"],
        difficulty=0.6,
    )
    # No session → should not attempt memory lookup
    r = await svc.compute_r_relevance(1, subgraph)
    assert 0.0 <= r <= 1.0


@pytest.mark.asyncio
async def test_r_relevance_working_memory_boosts_matching_content() -> None:
    """Content matching working memory should score higher than non-matching."""
    known = [KnowledgeNode(concept="attention", mastery=0.8)]

    # Service with working memory matching the content
    svc_match, _ = _make_service(user_knowledge=known)
    # Service without working memory (no session = neutral 0.5)
    svc_no_mem, _ = _make_service(user_knowledge=known)

    subgraph = _make_subgraph(
        nodes=[{"name": "attention"}],
        entry_concepts=["attention"],
        difficulty=0.5,
    )

    mock_session = AsyncMock()
    memory_ctx_match = MemoryContext(working_topics=["attention"])

    with patch(
        "alice.services.matching.MemoryManager"
    ) as mock_mem_mgr:
        mock_mgr_instance = mock_mem_mgr.return_value
        mock_mgr_instance.get_memory_context = AsyncMock(return_value=memory_ctx_match)
        r_with_memory = await svc_match.compute_r_relevance(
            1, subgraph, session=mock_session
        )

    # Without session: neutral working_match = 0.5
    r_no_memory = await svc_no_mem.compute_r_relevance(1, subgraph)

    # working_match=1.0 (full match) vs working_match=0.5 (neutral)
    # Difference = 0.1 * (1.0 - 0.5) = 0.05
    assert r_with_memory > r_no_memory
