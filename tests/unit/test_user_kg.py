"""Tests for UserKnowledgeGraph — user knowledge tracking in Neo4j."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from alice.graph.client import GraphClient
from alice.graph.user_kg import (
    KnowledgeGap,
    KnowledgeNode,
    MasteryLevel,
    UserKnowledgeGraph,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=GraphClient)
    client.execute_query.return_value = []
    return client


@pytest.fixture
def ukg(mock_client: AsyncMock) -> UserKnowledgeGraph:
    return UserKnowledgeGraph(client=mock_client)


# ── ensure_user_node ──────────────────────────────────────────────────────────


async def test_ensure_user_node_calls_merge_cypher(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """ensure_user_node executes MERGE User cypher."""
    await ukg.ensure_user_node(user_id=1)
    mock_client.execute_query.assert_called_once()
    cypher = mock_client.execute_query.call_args.args[0]
    assert "MERGE" in cypher
    assert "User" in cypher
    assert mock_client.execute_query.call_args.args[1] == {"user_id": 1}


# ── add_known_concept ─────────────────────────────────────────────────────────


async def test_add_known_concept_clamps_mastery_high(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """add_known_concept clamps mastery above 1.0 to 1.0."""
    await ukg.add_known_concept(user_id=1, concept="transformer", mastery=2.0)
    # Second call sets mastery — find it
    knows_call = mock_client.execute_query.call_args_list[1]
    assert knows_call.args[1]["mastery"] == 1.0


async def test_add_known_concept_clamps_mastery_low(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """add_known_concept clamps mastery below 0.0 to 0.0."""
    await ukg.add_known_concept(user_id=1, concept="transformer", mastery=-0.5)
    knows_call = mock_client.execute_query.call_args_list[1]
    assert knows_call.args[1]["mastery"] == 0.0


async def test_add_known_concept_calls_two_queries(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """add_known_concept runs 2 queries: concept upsert + KNOWS edge."""
    await ukg.add_known_concept(user_id=1, concept="attention", mastery=0.6)
    assert mock_client.execute_query.call_count == 2


async def test_add_known_concept_normal_mastery_unchanged(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """add_known_concept leaves mastery in [0, 1] unchanged."""
    await ukg.add_known_concept(user_id=1, concept="gpt", mastery=0.5)
    knows_call = mock_client.execute_query.call_args_list[1]
    assert knows_call.args[1]["mastery"] == pytest.approx(0.5)


# ── get_knowledge_map ─────────────────────────────────────────────────────────


async def test_get_knowledge_map_returns_nodes(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """get_knowledge_map parses Neo4j rows into KnowledgeNode list."""
    mock_client.execute_query.return_value = [
        {"concept": "transformer", "mastery": 0.8, "last_reviewed": None, "aliases": []},
        {
            "concept": "attention_mechanism",
            "mastery": 0.6,
            "last_reviewed": None,
            "aliases": ["注意力机制"],
        },
    ]
    result = await ukg.get_knowledge_map(user_id=1)
    assert len(result) == 2
    assert isinstance(result[0], KnowledgeNode)
    assert result[0].concept == "transformer"
    assert result[0].mastery == pytest.approx(0.8)
    assert result[1].aliases == ["注意力机制"]


async def test_get_knowledge_map_empty(ukg: UserKnowledgeGraph, mock_client: AsyncMock) -> None:
    """get_knowledge_map returns empty list when user has no known concepts."""
    mock_client.execute_query.return_value = []
    result = await ukg.get_knowledge_map(user_id=99)
    assert result == []


# ── get_knowledge_gaps ────────────────────────────────────────────────────────


async def test_get_knowledge_gaps_returns_gaps(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """get_knowledge_gaps parses Neo4j rows into KnowledgeGap list."""
    mock_client.execute_query.return_value = [
        {"concept": "linear_algebra", "required_by": "transformer"},
        {"concept": "neural_network", "required_by": "transformer"},
    ]
    result = await ukg.get_knowledge_gaps(user_id=1, concept="transformer")
    assert len(result) == 2
    assert isinstance(result[0], KnowledgeGap)
    assert result[0].concept == "linear_algebra"
    assert result[0].required_by == "transformer"


async def test_get_knowledge_gaps_empty(ukg: UserKnowledgeGraph, mock_client: AsyncMock) -> None:
    """get_knowledge_gaps returns empty list when no prerequisites missing."""
    mock_client.execute_query.return_value = []
    result = await ukg.get_knowledge_gaps(user_id=1, concept="hello_world")
    assert result == []


async def test_get_knowledge_gaps_query_includes_concept(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """get_knowledge_gaps passes correct concept name to query."""
    mock_client.execute_query.return_value = []
    await ukg.get_knowledge_gaps(user_id=7, concept="multi_head_attention")
    params = mock_client.execute_query.call_args.args[1]
    assert params["concept"] == "multi_head_attention"
    assert params["user_id"] == 7


# ── update_mastery ────────────────────────────────────────────────────────────


async def test_update_mastery_clamps_high(ukg: UserKnowledgeGraph, mock_client: AsyncMock) -> None:
    """update_mastery clamps value above 1.0 to 1.0."""
    await ukg.update_mastery(user_id=1, concept="gpt", new_mastery=1.5)
    params = mock_client.execute_query.call_args.args[1]
    assert params["mastery"] == 1.0


async def test_update_mastery_clamps_low(ukg: UserKnowledgeGraph, mock_client: AsyncMock) -> None:
    """update_mastery clamps value below 0.0 to 0.0."""
    await ukg.update_mastery(user_id=1, concept="gpt", new_mastery=-0.1)
    params = mock_client.execute_query.call_args.args[1]
    assert params["mastery"] == 0.0


async def test_update_mastery_calls_set_cypher(
    ukg: UserKnowledgeGraph, mock_client: AsyncMock
) -> None:
    """update_mastery runs MERGE + SET r.mastery Cypher (creates KNOWS if missing)."""
    await ukg.update_mastery(user_id=1, concept="attention", new_mastery=0.9)
    cypher = mock_client.execute_query.call_args.args[0]
    assert "MERGE" in cypher, "Should use MERGE to create KNOWS if missing"
    assert "SET" in cypher
    assert "mastery" in cypher
    params = mock_client.execute_query.call_args.args[1]
    assert params["mastery"] == pytest.approx(0.9)
    assert params["user_id"] == 1
    assert params["concept"] == "attention"


# ── MasteryLevel constants ────────────────────────────────────────────────────


def test_mastery_level_constants() -> None:
    assert MasteryLevel.UNKNOWN == 0.0
    assert MasteryLevel.AWARE == pytest.approx(0.3)
    assert MasteryLevel.UNDERSTANDS == pytest.approx(0.6)
    assert MasteryLevel.MASTERED == pytest.approx(0.9)
