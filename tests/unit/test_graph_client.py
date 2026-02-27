"""Unit tests for alice.graph — GraphClient, GraphRepository, schema constants."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alice.graph.client import GraphClient
from alice.graph.repository import GraphRepository
from alice.graph.schema import SCHEMA_STATEMENTS, NodeLabel, RelType

# ── Schema constants tests ──────────────────────────────────────────────────


def test_node_labels_defined():
    assert NodeLabel.CONCEPT == "Concept"
    assert NodeLabel.METHOD == "Method"
    assert NodeLabel.TOOL == "Tool"
    assert NodeLabel.THEORY == "Theory"
    assert NodeLabel.USER == "User"
    assert NodeLabel.CONTENT == "Content"


def test_rel_types_defined():
    assert RelType.KNOWS == "KNOWS"
    assert RelType.PREREQUISITE_OF == "PREREQUISITE_OF"
    assert RelType.EXTENDS == "EXTENDS"
    assert RelType.APPLIES_TO == "APPLIES_TO"
    assert RelType.DISCUSSES == "DISCUSSES"
    assert RelType.CONTRASTS == "CONTRASTS"


def test_schema_statements_not_empty():
    assert len(SCHEMA_STATEMENTS) >= 5
    for stmt in SCHEMA_STATEMENTS:
        assert "IF NOT EXISTS" in stmt


# ── GraphClient unit tests ──────────────────────────────────────────────────


@pytest.fixture
def mock_driver():
    """Mock AsyncDriver with a properly configured session context manager."""
    driver = AsyncMock()
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=[{"n": {"name": "test"}}])
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    driver.session = MagicMock(return_value=mock_session)
    return driver, mock_session


async def test_graph_client_connect_creates_driver():
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = AsyncMock()
        client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
        await client.connect()
        mock_gdb.driver.assert_called_once_with("bolt://localhost:7687", auth=("neo4j", "password"))
        await client.close()


async def test_graph_client_health_check_true(mock_driver):
    driver, _ = mock_driver
    driver.verify_connectivity = AsyncMock()
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = driver
        client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
        await client.connect()
        result = await client.health_check()
        assert result is True


async def test_graph_client_health_check_false_when_disconnected():
    client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
    # Not connected — driver is None
    result = await client.health_check()
    assert result is False


async def test_graph_client_health_check_false_on_exception(mock_driver):
    driver, _ = mock_driver
    driver.verify_connectivity = AsyncMock(side_effect=Exception("connection refused"))
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = driver
        client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
        await client.connect()
        result = await client.health_check()
        assert result is False


async def test_graph_client_execute_query_returns_data(mock_driver):
    driver, _ = mock_driver
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = driver
        client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
        await client.connect()
        rows = await client.execute_query("MATCH (n) RETURN n LIMIT 1")
        assert isinstance(rows, list)


async def test_graph_client_execute_query_raises_when_not_connected():
    client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
    with pytest.raises(RuntimeError, match="not connected"):
        await client.execute_query("MATCH (n) RETURN n")


async def test_graph_client_context_manager():
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_driver_inst = AsyncMock()
        mock_gdb.driver.return_value = mock_driver_inst
        async with GraphClient("bolt://localhost:7687", ("neo4j", "password")) as client:
            assert client._driver is not None
        mock_driver_inst.close.assert_awaited_once()


async def test_ensure_schema_runs_all_statements(mock_driver):
    driver, mock_session = mock_driver
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=[])
    mock_session.run = AsyncMock(return_value=mock_result)
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = driver
        client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
        await client.connect()
        await client.ensure_schema()
        assert mock_session.run.call_count == len(SCHEMA_STATEMENTS)


async def test_graph_client_close_clears_driver():
    with patch("alice.graph.client.AsyncGraphDatabase") as mock_gdb:
        mock_driver_inst = AsyncMock()
        mock_gdb.driver.return_value = mock_driver_inst
        client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
        await client.connect()
        assert client._driver is not None
        await client.close()
        assert client._driver is None


async def test_graph_client_close_idempotent():
    """Calling close() when already disconnected should not raise."""
    client = GraphClient("bolt://localhost:7687", ("neo4j", "password"))
    await client.close()  # Should not raise
    assert client._driver is None


# ── GraphRepository unit tests ──────────────────────────────────────────────


@pytest.fixture
def mock_graph_client():
    client = AsyncMock(spec=GraphClient)
    client.execute_query = AsyncMock(return_value=[{"c": {"name": "transformer", "aliases": []}}])
    return client


async def test_upsert_concept_calls_merge(mock_graph_client):
    repo = GraphRepository(mock_graph_client)
    result = await repo.upsert_concept("transformer", NodeLabel.CONCEPT, ["变换器"])
    assert result == {"name": "transformer", "aliases": []}
    mock_graph_client.execute_query.assert_awaited_once()
    call_args = mock_graph_client.execute_query.call_args
    # parameters dict is the second positional arg
    params = call_args[0][1]
    assert params["name"] == "transformer"
    assert "变换器" in params["aliases"]


async def test_upsert_concept_returns_node(mock_graph_client):
    repo = GraphRepository(mock_graph_client)
    result = await repo.upsert_concept("transformer")
    assert result == {"name": "transformer", "aliases": []}


async def test_upsert_concept_returns_empty_dict_when_no_rows():
    client = AsyncMock(spec=GraphClient)
    client.execute_query = AsyncMock(return_value=[])
    repo = GraphRepository(client)
    result = await repo.upsert_concept("unknown")
    assert result == {}


async def test_upsert_concept_default_aliases(mock_graph_client):
    """upsert_concept without aliases passes empty list."""
    repo = GraphRepository(mock_graph_client)
    await repo.upsert_concept("attention")
    params = mock_graph_client.execute_query.call_args[0][1]
    assert params["aliases"] == []


async def test_create_relationship_calls_match_merge(mock_graph_client):
    mock_graph_client.execute_query = AsyncMock(return_value=[])
    repo = GraphRepository(mock_graph_client)
    await repo.create_relationship(
        "transformer",
        NodeLabel.CONCEPT,
        "attention",
        NodeLabel.CONCEPT,
        RelType.EXTENDS,
    )
    mock_graph_client.execute_query.assert_awaited_once()
    call_args = mock_graph_client.execute_query.call_args
    params = call_args[0][1]
    assert params["from_name"] == "transformer"
    assert params["to_name"] == "attention"
    assert params["props"] == {}


async def test_create_relationship_with_properties(mock_graph_client):
    mock_graph_client.execute_query = AsyncMock(return_value=[])
    repo = GraphRepository(mock_graph_client)
    await repo.create_relationship(
        "transformer",
        NodeLabel.CONCEPT,
        "attention",
        NodeLabel.CONCEPT,
        RelType.EXTENDS,
        properties={"weight": 0.9},
    )
    params = mock_graph_client.execute_query.call_args[0][1]
    assert params["props"] == {"weight": 0.9}


async def test_get_user_knowledge_returns_list(mock_graph_client):
    mock_graph_client.execute_query = AsyncMock(
        return_value=[{"name": "transformers", "labels": ["Concept"], "aliases": []}]
    )
    repo = GraphRepository(mock_graph_client)
    result = await repo.get_user_knowledge(user_id=1)
    assert isinstance(result, list)
    assert result[0]["name"] == "transformers"


async def test_get_user_knowledge_passes_user_id(mock_graph_client):
    mock_graph_client.execute_query = AsyncMock(return_value=[])
    repo = GraphRepository(mock_graph_client)
    await repo.get_user_knowledge(user_id=42)
    params = mock_graph_client.execute_query.call_args[0][1]
    assert params["user_id"] == 42


async def test_get_content_subgraph_returns_list(mock_graph_client):
    mock_graph_client.execute_query = AsyncMock(
        side_effect=[
            [{"name": "attention", "labels": ["Concept"]}],  # nodes query
            [{"from_name": "attention", "relation": "PREREQUISITE_OF", "to_name": "transformer"}],  # edges query
        ]
    )
    repo = GraphRepository(mock_graph_client)
    result = await repo.get_content_subgraph(content_id=42)
    assert isinstance(result, dict)
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["name"] == "attention"


async def test_get_content_subgraph_passes_content_id(mock_graph_client):
    mock_graph_client.execute_query = AsyncMock(return_value=[])
    repo = GraphRepository(mock_graph_client)
    await repo.get_content_subgraph(content_id=99)
    params = mock_graph_client.execute_query.call_args[0][1]
    assert params["content_id"] == 99
