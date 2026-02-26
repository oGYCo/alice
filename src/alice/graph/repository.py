"""Graph CRUD operations — concepts, relationships, user knowledge, content subgraph."""

from __future__ import annotations

from typing import Any, Protocol, cast

import structlog

from alice.graph.client import GraphClient
from alice.graph.schema import NodeLabel, RelType


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

    async def get_content_subgraph(self, content_id: int) -> list[dict[str, Any]]:
        """Return all nodes and relationships connected to a Content node."""
        cypher = "MATCH (c:Content {id: $content_id})-[r]->(n) RETURN c, type(r) AS rel_type, n"
        return await self._client.execute_query(cypher, {"content_id": content_id})
