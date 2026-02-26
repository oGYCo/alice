"""Tests for SubgraphExtractor — content subgraph generation via LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from alice.graph.extractor import (
    ContentSubgraph,
    ContentSubgraphEdge,
    ContentSubgraphNode,
    SubgraphExtractor,
)
from alice.graph.repository import GraphRepository
from alice.graph.schema import NodeLabel, RelType
from alice.llm.protocol import LLMClient


def _make_simple_subgraph(num_nodes: int = 2) -> ContentSubgraph:
    """Create a test subgraph fixture."""
    nodes = [
        ContentSubgraphNode(name=f"concept_{i}", type="concept", aliases=[])
        for i in range(num_nodes)
    ]
    edges = []
    if num_nodes >= 2:
        edges = [
            ContentSubgraphEdge(
                **{"from": "concept_0", "to": "concept_1", "relation": "prerequisite"}
            )
        ]
    return ContentSubgraph(
        nodes=nodes,
        edges=edges,
        difficulty=0.5,
        entry_concepts=["concept_0"],
    )


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock(spec=LLMClient)
    llm.complete_structured.return_value = _make_simple_subgraph()
    return llm


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock(spec=GraphRepository)
    repo.upsert_concept.return_value = {}
    repo.create_relationship.return_value = None
    return repo


@pytest.fixture
def extractor(mock_llm: AsyncMock, mock_repo: AsyncMock) -> SubgraphExtractor:
    return SubgraphExtractor(llm=mock_llm, graph_repo=mock_repo)


async def test_extract_stores_nodes(extractor: SubgraphExtractor, mock_repo: AsyncMock) -> None:
    """extract() calls upsert_concept for each node."""
    result = await extractor.extract(
        content_id=42, title="Test", summary="Summary", key_points=["Point A"]
    )
    assert len(result.nodes) == 2
    assert mock_repo.upsert_concept.call_count == 2


async def test_extract_creates_discusses_relationships(
    extractor: SubgraphExtractor, mock_repo: AsyncMock
) -> None:
    """extract() creates DISCUSSES links from content to each concept."""
    await extractor.extract(content_id=42, title="Test", summary="Summary", key_points=["Point A"])
    discusses_calls = [
        call
        for call in mock_repo.create_relationship.call_args_list
        if call.args[4] == RelType.DISCUSSES
        or (len(call.args) > 4 and call.args[4] == RelType.DISCUSSES)
    ]
    # One DISCUSSES per node (2 nodes) + edge calls
    assert len(discusses_calls) == 2


async def test_extract_creates_edge_relationships(
    extractor: SubgraphExtractor, mock_repo: AsyncMock
) -> None:
    """extract() creates PREREQUISITE_OF edge from concept_0 → concept_1."""
    await extractor.extract(content_id=42, title="Test", summary="Summary", key_points=[])
    # 2 DISCUSSES calls + 1 PREREQUISITE_OF edge call = 3 total
    assert mock_repo.create_relationship.call_count == 3


async def test_max_10_nodes_enforced(extractor: SubgraphExtractor, mock_llm: AsyncMock) -> None:
    """extract() truncates nodes to 10 when LLM returns more."""
    big_subgraph = _make_simple_subgraph(num_nodes=15)
    mock_llm.complete_structured.return_value = big_subgraph
    result = await extractor.extract(
        content_id=1, title="Big", summary="Big article", key_points=[]
    )
    assert len(result.nodes) == 10


async def test_difficulty_clamped_low(extractor: SubgraphExtractor, mock_llm: AsyncMock) -> None:
    """extract() clamps difficulty below 0.0 to 0.0."""
    subgraph = _make_simple_subgraph()
    subgraph.difficulty = -0.5
    mock_llm.complete_structured.return_value = subgraph
    result = await extractor.extract(content_id=1, title="T", summary="S", key_points=[])
    assert result.difficulty == 0.0


async def test_difficulty_clamped_high(extractor: SubgraphExtractor, mock_llm: AsyncMock) -> None:
    """extract() clamps difficulty above 1.0 to 1.0."""
    subgraph = _make_simple_subgraph()
    subgraph.difficulty = 1.5
    mock_llm.complete_structured.return_value = subgraph
    result = await extractor.extract(content_id=1, title="T", summary="S", key_points=[])
    assert result.difficulty == 1.0


async def test_difficulty_within_range_unchanged(
    extractor: SubgraphExtractor, mock_llm: AsyncMock
) -> None:
    """extract() leaves difficulty in [0, 1] unchanged."""
    subgraph = _make_simple_subgraph()
    subgraph.difficulty = 0.7
    mock_llm.complete_structured.return_value = subgraph
    result = await extractor.extract(content_id=1, title="T", summary="S", key_points=[])
    assert result.difficulty == pytest.approx(0.7)


def test_map_relation_prerequisite(extractor: SubgraphExtractor) -> None:
    assert extractor._map_relation_to_reltype("prerequisite") == RelType.PREREQUISITE_OF


def test_map_relation_extends(extractor: SubgraphExtractor) -> None:
    assert extractor._map_relation_to_reltype("extends") == RelType.EXTENDS


def test_map_relation_applies_to(extractor: SubgraphExtractor) -> None:
    assert extractor._map_relation_to_reltype("applies_to") == RelType.APPLIES_TO


def test_map_relation_contrasts(extractor: SubgraphExtractor) -> None:
    assert extractor._map_relation_to_reltype("contrasts") == RelType.CONTRASTS


def test_map_relation_unknown_defaults_to_extends(extractor: SubgraphExtractor) -> None:
    assert extractor._map_relation_to_reltype("unknown_rel") == RelType.EXTENDS


def test_map_type_concept(extractor: SubgraphExtractor) -> None:
    assert extractor._map_type_to_label("concept") == NodeLabel.CONCEPT


def test_map_type_method(extractor: SubgraphExtractor) -> None:
    assert extractor._map_type_to_label("method") == NodeLabel.METHOD


def test_map_type_tool(extractor: SubgraphExtractor) -> None:
    assert extractor._map_type_to_label("tool") == NodeLabel.TOOL


def test_map_type_theory(extractor: SubgraphExtractor) -> None:
    assert extractor._map_type_to_label("theory") == NodeLabel.THEORY


def test_map_type_unknown_defaults_to_concept(extractor: SubgraphExtractor) -> None:
    assert extractor._map_type_to_label("unknown_type") == NodeLabel.CONCEPT


async def test_llm_prompt_rendered_with_correct_args(
    extractor: SubgraphExtractor, mock_llm: AsyncMock
) -> None:
    """extract() renders prompt with title, summary, key_points."""
    await extractor.extract(
        content_id=5,
        title="Attention Is All You Need",
        summary="Introduces transformers",
        key_points=["self-attention", "multi-head attention"],
    )
    mock_llm.complete_structured.assert_called_once()
    call_kwargs = mock_llm.complete_structured.call_args
    # First arg is prompt string, second is ContentSubgraph model
    assert "Attention Is All You Need" in call_kwargs.args[0]
    assert call_kwargs.args[1] == ContentSubgraph
