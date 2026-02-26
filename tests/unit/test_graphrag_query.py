"""Unit tests for GraphRAGQueryEngine — hybrid query engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from alice.graph.user_kg import KnowledgeNode
from alice.services.graphrag_query import (
    GRAPHRAG_GRAPH_WEIGHT,
    GRAPHRAG_TEXT_WEIGHT,
    GraphHit,
    GraphRAGQueryEngine,
    QueryMode,
    RankedResult,
    SemanticHit,
    TextHit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(
    graph_rows: list[dict] | None = None,
    search_hits: list[dict] | None = None,
    llm_response: str = '["attention_mechanism"]',
    user_knowledge: list[KnowledgeNode] | None = None,
) -> GraphRAGQueryEngine:
    """Build a GraphRAGQueryEngine with mocked backends."""
    # Mock GraphClient
    graph_client = MagicMock()
    graph_client.execute_query = AsyncMock(return_value=graph_rows or [])

    # Mock SearchService
    search_service = MagicMock()
    search_service.search = MagicMock(return_value={"hits": search_hits or []})

    # Mock LLMClient
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)

    engine = GraphRAGQueryEngine(graph_client, search_service, llm_client)

    # Patch user KG
    engine._user_kg = MagicMock()
    engine._user_kg.get_knowledge_map = AsyncMock(return_value=user_knowledge or [])

    return engine


# ---------------------------------------------------------------------------
# Tests — graph search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_search_returns_hits_from_neo4j() -> None:
    """Graph search converts Neo4j rows into GraphHit objects."""
    rows = [{"content_id": "42", "min_dist": 1}]
    engine = _make_engine(graph_rows=rows)
    hits = await engine._graph_search(["attention_mechanism"], user_id=1)
    assert len(hits) == 1
    assert hits[0].content_id == "42"
    assert hits[0].hop_distance == 1
    # score = 1/(1+1) = 0.5
    assert hits[0].score == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_graph_search_empty_concepts_returns_nothing() -> None:
    """No concepts → graph search skips Neo4j and returns empty list."""
    engine = _make_engine()
    hits = await engine._graph_search([], user_id=1)
    assert hits == []
    engine._graph.execute_query.assert_not_called()


@pytest.mark.asyncio
async def test_graph_search_neo4j_failure_returns_empty() -> None:
    """If Neo4j raises exception, graph search returns [] gracefully."""
    engine = _make_engine()
    engine._graph.execute_query = AsyncMock(side_effect=Exception("Neo4j unavailable"))
    hits = await engine._graph_search(["ml"], user_id=1)
    assert hits == []


@pytest.mark.asyncio
async def test_graph_search_closer_concepts_score_higher() -> None:
    """Hop distance 0 should score higher than hop distance 2."""
    rows = [
        {"content_id": "1", "min_dist": 0},
        {"content_id": "2", "min_dist": 2},
    ]
    engine = _make_engine(graph_rows=rows)
    hits = await engine._graph_search(["ml"], user_id=1)
    scores = {h.content_id: h.score for h in hits}
    assert scores["1"] > scores["2"]


# ---------------------------------------------------------------------------
# Tests — text search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_search_returns_hits_from_meilisearch() -> None:
    """Text search converts Meilisearch hits into TextHit objects."""
    search_hits = [
        {
            "id": "10",
            "title": "Transformers paper",
            "_formatted": {"title": "<em>Transformers</em>", "summary": ""},
        },
        {
            "id": "11",
            "title": "Attention is all you need",
            "_formatted": {"title": "Attention...", "summary": ""},
        },
    ]
    engine = _make_engine(search_hits=search_hits)
    hits = await engine._text_search("transformer architecture")
    assert len(hits) == 2
    assert hits[0].content_id == "10"
    # First hit has score 1.0, second hit has lower score
    assert hits[0].score > hits[1].score


@pytest.mark.asyncio
async def test_text_search_meilisearch_failure_returns_empty() -> None:
    """If Meilisearch raises, text search returns [] gracefully."""
    engine = _make_engine()
    engine._search.search = MagicMock(side_effect=Exception("Meilisearch down"))
    hits = await engine._text_search("attention mechanism")
    assert hits == []


# ---------------------------------------------------------------------------
# Tests — semantic search (stub)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_stub() -> None:
    """Phase 2: semantic search is a stub, always returns empty list."""
    engine = _make_engine()
    hits = await engine._semantic_search("some query")
    assert hits == []


# ---------------------------------------------------------------------------
# Tests — query() happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_hybrid_returns_merged_results() -> None:
    """Happy path: hybrid query returns merged, ranked results."""
    graph_rows = [{"content_id": "1", "min_dist": 1}, {"content_id": "2", "min_dist": 2}]
    search_hits = [
        {"id": "2", "_formatted": {"title": "", "summary": ""}},
        {"id": "3", "_formatted": {"title": "", "summary": ""}},
    ]
    engine = _make_engine(graph_rows=graph_rows, search_hits=search_hits)
    results = await engine.query("attention mechanism optimization", user_id=1)
    assert len(results) >= 2
    # Should contain at least content_id "2" (found in both graph and text)
    ids = [r.content_id for r in results]
    assert "2" in ids
    # Results should be ranked in descending order
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score


@pytest.mark.asyncio
async def test_query_deduplicates_same_content_from_multiple_sources() -> None:
    """Content found in both graph and text should appear only once."""
    graph_rows = [{"content_id": "42", "min_dist": 0}]
    search_hits = [{"id": "42", "_formatted": {"title": "test", "summary": ""}}]
    engine = _make_engine(graph_rows=graph_rows, search_hits=search_hits)
    results = await engine.query("test query", user_id=1)
    content_ids = [r.content_id for r in results]
    assert content_ids.count("42") == 1


@pytest.mark.asyncio
async def test_query_result_sources_labeled_correctly() -> None:
    """Results include correct source label(s)."""
    graph_rows = [{"content_id": "99", "min_dist": 1}]
    search_hits = []
    engine = _make_engine(graph_rows=graph_rows, search_hits=search_hits)
    results = await engine.query("test", user_id=1)
    assert any(r.content_id == "99" for r in results)
    r = next(r for r in results if r.content_id == "99")
    assert "graph" in r.source


@pytest.mark.asyncio
async def test_query_respects_limit() -> None:
    """query() returns at most `limit` results."""
    # Create 10 graph hits
    graph_rows = [{"content_id": str(i), "min_dist": i % 4} for i in range(10)]
    engine = _make_engine(graph_rows=graph_rows)
    results = await engine.query("test", user_id=1, limit=3)
    assert len(results) <= 3


# ---------------------------------------------------------------------------
# Tests — graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_neo4j_unavailable_returns_text_only_results() -> None:
    """If Neo4j is down, query falls back to text-only results without exception."""
    engine = _make_engine(
        search_hits=[{"id": "5", "_formatted": {"title": "text result", "summary": ""}}]
    )
    engine._graph.execute_query = AsyncMock(side_effect=Exception("Neo4j down"))
    results = await engine.query("test query", user_id=1)
    # Should get text results even though graph failed
    assert all(r.graph_score == 0.0 for r in results)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_both_backends_unavailable_returns_empty() -> None:
    """If all backends fail, query returns empty list without exception."""
    engine = _make_engine()
    engine._graph.execute_query = AsyncMock(side_effect=Exception("Neo4j down"))
    engine._search.search = MagicMock(side_effect=Exception("Meilisearch down"))
    results = await engine.query("test query", user_id=1)
    assert results == []


# ---------------------------------------------------------------------------
# Tests — weight-based merging
# ---------------------------------------------------------------------------


def test_merge_and_rank_weights_applied_correctly() -> None:
    """Weighted merge produces scores proportional to configured weights."""
    engine = _make_engine()
    graph_hits = [GraphHit(content_id="A", score=1.0)]
    text_hits = [TextHit(content_id="B", score=1.0)]
    semantic_hits = [SemanticHit(content_id="C", score=1.0)]

    results = engine._merge_and_rank(graph_hits, text_hits, semantic_hits)
    by_id = {r.content_id: r for r in results}

    # A has only graph score → its final score = gw * 1.0 / total_weight
    total = engine._graph_weight + engine._text_weight + engine._semantic_weight
    expected_a = (engine._graph_weight / total) * 1.0
    assert by_id["A"].score == pytest.approx(expected_a)


def test_merge_redistributes_weight_when_backend_empty() -> None:
    """If graph returns no hits, its weight is redistributed to text + semantic."""
    engine = _make_engine()
    text_hits = [TextHit(content_id="X", score=1.0)]
    results = engine._merge_and_rank([], text_hits, [])
    # Only text backend has hits → text weight = 1.0 → final score for X = 1.0
    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0)


def test_merge_empty_all_returns_empty() -> None:
    """All backends empty → merge returns empty list."""
    engine = _make_engine()
    results = engine._merge_and_rank([], [], [])
    assert results == []


# ---------------------------------------------------------------------------
# Tests — concept extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_concepts_parses_llm_json() -> None:
    """LLM returning valid JSON array → concepts are parsed."""
    engine = _make_engine(llm_response='["attention_mechanism", "transformer"]')
    concepts = await engine._extract_query_concepts("attention in transformers")
    assert "attention_mechanism" in concepts
    assert "transformer" in concepts


@pytest.mark.asyncio
async def test_extract_concepts_fallback_on_llm_failure() -> None:
    """LLM failure → fallback to word splitting."""
    engine = _make_engine()
    engine._llm.complete = AsyncMock(side_effect=Exception("LLM down"))
    concepts = await engine._extract_query_concepts("attention mechanism neural network")
    # Should get words from the query
    assert len(concepts) > 0


@pytest.mark.asyncio
async def test_extract_concepts_fallback_on_invalid_json() -> None:
    """LLM returning non-JSON → fallback to word splitting."""
    engine = _make_engine(llm_response="here are the concepts: attention, transformer")
    concepts = await engine._extract_query_concepts("attention transformer")
    assert len(concepts) > 0
