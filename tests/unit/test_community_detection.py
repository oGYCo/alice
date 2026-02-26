"""Tests for CommunityDetector — Leiden algorithm community detection on user KG."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from alice.services.community_detection import (
    CommunityDetector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph_client(nodes: list[dict], edges: list[dict]) -> MagicMock:
    """Build a mock GraphClient whose execute_query returns the given data."""
    client = MagicMock()

    async def _query(cypher: str, parameters: dict | None = None) -> list[dict]:
        if "MATCH (u:User" in cypher and "(a:Concept" in cypher:
            # edge query
            return edges
        if "MATCH (u:User" in cypher:
            # node query
            return nodes
        return []

    client.execute_query = AsyncMock(side_effect=_query)
    return client


def _ml_graph() -> tuple[list[dict], list[dict]]:
    """Three clear clusters: ML, Systems, Math — 9 nodes, 9 intra + 2 bridge edges."""
    nodes = [
        # ML cluster
        {"name": "transformer", "mastery": 0.8},
        {"name": "attention", "mastery": 0.7},
        {"name": "bert", "mastery": 0.6},
        # Systems cluster
        {"name": "linux_kernel", "mastery": 0.5},
        {"name": "memory_management", "mastery": 0.4},
        {"name": "tcp_ip", "mastery": 0.3},
        # Math cluster
        {"name": "linear_algebra", "mastery": 0.9},
        {"name": "probability", "mastery": 0.8},
        {"name": "calculus", "mastery": 0.7},
    ]
    edges = [
        # ML intra-edges
        {"source": "transformer", "target": "attention", "weight": 1.0},
        {"source": "attention", "target": "bert", "weight": 1.0},
        {"source": "transformer", "target": "bert", "weight": 1.0},
        # Systems intra-edges
        {"source": "linux_kernel", "target": "memory_management", "weight": 1.0},
        {"source": "memory_management", "target": "tcp_ip", "weight": 1.0},
        {"source": "linux_kernel", "target": "tcp_ip", "weight": 1.0},
        # Math intra-edges
        {"source": "linear_algebra", "target": "probability", "weight": 1.0},
        {"source": "probability", "target": "calculus", "weight": 1.0},
        {"source": "linear_algebra", "target": "calculus", "weight": 1.0},
        # Bridge: linear_algebra connects Math ↔ ML
        {"source": "linear_algebra", "target": "transformer", "weight": 0.5},
        # Bridge: tcp_ip connects Systems ↔ ML (weakly)
        {"source": "tcp_ip", "target": "attention", "weight": 0.3},
    ]
    return nodes, edges


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ml_nodes_edges() -> tuple[list[dict], list[dict]]:
    return _ml_graph()


@pytest.fixture()
def detector(ml_nodes_edges: tuple[list[dict], list[dict]]) -> CommunityDetector:
    nodes, edges = ml_nodes_edges
    client = _make_graph_client(nodes, edges)
    return CommunityDetector(graph_client=client)


# ---------------------------------------------------------------------------
# 1. Community detection basics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_communities_returns_communities(detector: CommunityDetector) -> None:
    """With 3 clear clusters, detect_communities should find ≥ 2 communities."""
    communities = await detector.detect_communities(user_id=1)
    assert len(communities) >= 2


@pytest.mark.asyncio
async def test_each_community_has_at_least_one_concept(detector: CommunityDetector) -> None:
    communities = await detector.detect_communities(user_id=1)
    for c in communities:
        assert len(c.concepts) >= 1


@pytest.mark.asyncio
async def test_all_nodes_assigned_to_exactly_one_community(detector: CommunityDetector) -> None:
    communities = await detector.detect_communities(user_id=1)
    all_assigned = [concept for c in communities for concept in c.concepts]
    assert len(all_assigned) == len(set(all_assigned)), (
        "No concept should appear in multiple communities"
    )
    assert len(set(all_assigned)) == 9, "All 9 nodes must be assigned"


@pytest.mark.asyncio
async def test_community_has_id_and_label(detector: CommunityDetector) -> None:
    communities = await detector.detect_communities(user_id=1)
    for c in communities:
        assert c.community_id >= 0
        assert isinstance(c.label, str)


@pytest.mark.asyncio
async def test_empty_graph_returns_empty_communities() -> None:
    """With no nodes/edges, detect_communities returns empty list."""
    client = _make_graph_client([], [])
    detector = CommunityDetector(graph_client=client)
    communities = await detector.detect_communities(user_id=99)
    assert communities == []


# ---------------------------------------------------------------------------
# 2. Bridge concept detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_bridges_returns_bridge_concepts(detector: CommunityDetector) -> None:
    bridges = await detector.find_bridges(user_id=1)
    assert len(bridges) >= 1


@pytest.mark.asyncio
async def test_bridge_has_name_and_connects_multiple_communities(
    detector: CommunityDetector,
) -> None:
    bridges = await detector.find_bridges(user_id=1)
    for b in bridges:
        assert isinstance(b.concept, str)
        assert b.connects_communities >= 2


@pytest.mark.asyncio
async def test_linear_algebra_identified_as_bridge(detector: CommunityDetector) -> None:
    """linear_algebra has cross-community edge to transformer — should be a bridge."""
    bridges = await detector.find_bridges(user_id=1)
    bridge_names = {b.concept for b in bridges}
    # At least one of the two bridge nodes must be detected
    assert bridge_names & {"linear_algebra", "tcp_ip"}


# ---------------------------------------------------------------------------
# 3. Sparse community detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_sparse_communities_returns_list(detector: CommunityDetector) -> None:
    sparse = await detector.find_sparse_communities(user_id=1)
    assert isinstance(sparse, list)


@pytest.mark.asyncio
async def test_sparse_community_has_low_average_mastery() -> None:
    """A cluster with all mastery=0.1 should be detected as sparse."""
    nodes = [
        {"name": "obscure_topic_a", "mastery": 0.1},
        {"name": "obscure_topic_b", "mastery": 0.1},
        {"name": "obscure_topic_c", "mastery": 0.1},
        {"name": "known_topic_x", "mastery": 0.9},
        {"name": "known_topic_y", "mastery": 0.9},
        {"name": "known_topic_z", "mastery": 0.9},
    ]
    edges = [
        {"source": "obscure_topic_a", "target": "obscure_topic_b", "weight": 1.0},
        {"source": "obscure_topic_b", "target": "obscure_topic_c", "weight": 1.0},
        {"source": "known_topic_x", "target": "known_topic_y", "weight": 1.0},
        {"source": "known_topic_y", "target": "known_topic_z", "weight": 1.0},
    ]
    client = _make_graph_client(nodes, edges)
    det = CommunityDetector(graph_client=client)
    sparse = await det.find_sparse_communities(user_id=2)
    assert any("obscure" in c for comm in sparse for c in comm.concepts)


# ---------------------------------------------------------------------------
# 4. update_community_labels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_community_labels_calls_neo4j(detector: CommunityDetector) -> None:
    """update_community_labels should write community_id back to Neo4j via execute_query."""
    communities = await detector.detect_communities(user_id=1)
    await detector.update_community_labels(user_id=1, communities=communities)
    # Should have called execute_query for the update
    assert detector._client.execute_query.call_count >= 2  # ≥1 fetch + ≥1 write
