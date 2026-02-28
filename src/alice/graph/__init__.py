"""Alice knowledge graph package — Neo4j client, schema, repository."""

from alice.graph.client import (
    GraphClient,
    close_shared_graph_client,
    get_shared_graph_client,
    make_edge_id,
    parse_edge_id,
)
from alice.graph.repository import GraphRepository
from alice.graph.schema import NodeLabel, RelType

__all__ = [
    "GraphClient",
    "GraphRepository",
    "NodeLabel",
    "RelType",
    "get_shared_graph_client",
    "close_shared_graph_client",
    "make_edge_id",
    "parse_edge_id",
]
