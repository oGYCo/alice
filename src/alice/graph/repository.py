"""Graph CRUD operations — concepts, relationships, user knowledge, content subgraph."""

from __future__ import annotations

from typing import Any, Protocol, cast

import structlog

from alice.graph.client import GraphClient
from alice.graph.schema import NodeLabel


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


class GraphRepository:
    """CRUD layer for the Alice knowledge graph."""

    def __init__(self, client: GraphClient) -> None:
        self._client = client

    async def upsert_concept(
        self,
        name: str,
        label: str = NodeLabel.CONCEPT,
        aliases: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create or update a concept node. English canonical name required."""
        cypher = f"MERGE (c:{label} {{name: $name}}) SET c.aliases = $aliases RETURN c"
        rows = await self._client.execute_query(cypher, {"name": name, "aliases": aliases or []})
        logger.info("concept_upserted", name=name, label=label)
        return rows[0]["c"] if rows else {}

    async def create_relationship(
        self,
        from_name: str,
        from_label: str,
        to_name: str,
        to_label: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a relationship between two nodes (MERGE — idempotent)."""
        cypher = (
            f"MATCH (a:{from_label} {{name: $from_name}}) "
            f"MATCH (b:{to_label} {{name: $to_name}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $props"
        )
        await self._client.execute_query(
            cypher,
            {
                "from_name": from_name,
                "to_name": to_name,
                "props": properties or {},
            },
        )
        logger.info(
            "relationship_created",
            from_name=from_name,
            to_name=to_name,
            rel_type=rel_type,
        )

    async def get_user_knowledge(self, user_id: int) -> list[dict[str, Any]]:
        """Return all concepts the user KNOWS."""
        cypher = (
            "MATCH (u:User {id: $user_id})-[:KNOWS]->(c) "
            "RETURN c.name AS name, labels(c) AS labels, c.aliases AS aliases"
        )
        return await self._client.execute_query(cypher, {"user_id": user_id})

    async def upsert_content_node(self, content_id: int) -> None:
        """Create or update a Content node (keyed by integer id)."""
        cypher = "MERGE (c:Content {id: $id}) RETURN c"
        await self._client.execute_query(cypher, {"id": content_id})
        logger.debug("content_node_upserted", content_id=content_id)

    async def link_content_to_concept(
        self,
        content_id: int,
        concept_name: str,
        concept_label: str,
    ) -> None:
        """Create DISCUSSES relationship from a Content node to a concept node."""
        cypher = (
            f"MATCH (c:Content {{id: $content_id}}) "
            f"MATCH (n:{concept_label} {{name: $name}}) "
            "MERGE (c)-[:DISCUSSES]->(n)"
        )
        await self._client.execute_query(
            cypher, {"content_id": content_id, "name": concept_name}
        )

    async def get_content_subgraph(self, content_id: int) -> dict[str, Any]:
        """Return nodes and edges of content's concept subgraph.

        Returns a dict with 'nodes' (list of {id, name, label, mastery})
        and 'edges' (list of {from_, to, relation}).
        """
        # Query 1: all concept nodes linked to this content
        nodes_cypher = (
            "MATCH (c:Content {id: $content_id})-[:DISCUSSES]->(n) "
            "RETURN n.name AS name, labels(n) AS labels"
        )
        node_rows = await self._client.execute_query(nodes_cypher, {"content_id": content_id})

        if not node_rows:
            return {"nodes": [], "edges": []}

        node_names = [r["name"] for r in node_rows]

        # Query 2: edges between those concept nodes
        edges_cypher = (
            "MATCH (c:Content {id: $content_id})-[:DISCUSSES]->(n1)-[r]->(n2) "
            "WHERE (c)-[:DISCUSSES]->(n2) "
            "RETURN n1.name AS from_name, type(r) AS relation, n2.name AS to_name"
        )
        edge_rows = await self._client.execute_query(edges_cypher, {"content_id": content_id})

        nodes = [
            {
                "id": r["name"],
                "name": r["name"],
                "label": r["labels"][0] if r.get("labels") else "Concept",
                "mastery": 0.5,
            }
            for r in node_rows
        ]
        edges = [
            {
                "from": r["from_name"],
                "to": r["to_name"],
                "relation": r["relation"].lower(),
            }
            for r in edge_rows
            if r["from_name"] in node_names and r["to_name"] in node_names
        ]
        return {"nodes": nodes, "edges": edges}
