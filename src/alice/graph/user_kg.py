"""User Knowledge Graph — tracks user's known concepts with mastery levels."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, cast

import structlog
from pydantic import BaseModel

from alice.graph.client import GraphClient
from alice.graph.schema import NodeLabel, RelType


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


class MasteryLevel:
    """Standard mastery levels for user knowledge tracking."""

    UNKNOWN = 0.0
    AWARE = 0.3
    UNDERSTANDS = 0.6
    MASTERED = 0.9


class KnowledgeNode(BaseModel):
    """A concept the user knows, with mastery level."""

    concept: str
    mastery: float  # 0.0 to 1.0
    last_reviewed: datetime | None = None
    aliases: list[str] = []


class KnowledgeGap(BaseModel):
    """A missing prerequisite concept for a given target concept."""

    concept: str  # The missing prerequisite
    required_by: str  # The concept that needs it


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class UserKnowledgeGraph:
    """Manages the user's personal knowledge graph in Neo4j."""

    def __init__(self, client: GraphClient) -> None:
        self._client = client

    async def ensure_user_node(self, user_id: int) -> None:
        """Create User node if it doesn't exist (MERGE — idempotent)."""
        cypher = "MERGE (u:User {id: $user_id}) ON CREATE SET u.created_at = datetime()"
        await self._client.execute_query(cypher, {"user_id": user_id})
        logger.info("user_node_ensured", user_id=user_id)

    async def add_known_concept(
        self,
        user_id: int,
        concept: str,
        mastery: float,
        aliases: list[str] | None = None,
    ) -> None:
        """Add or update a KNOWS relationship from User → Concept.

        Creates concept node if missing. Clamps mastery to [0.0, 1.0].
        """
        mastery = _clamp(mastery)
        # Upsert concept node first
        cypher_concept = "MERGE (c:Concept {name: $concept}) ON CREATE SET c.aliases = $aliases"
        await self._client.execute_query(
            cypher_concept,
            {"concept": concept, "aliases": aliases or []},
        )
        # Upsert KNOWS relationship
        cypher_knows = (
            "MATCH (u:User {id: $user_id}) "
            "MATCH (c:Concept {name: $concept}) "
            "MERGE (u)-[r:KNOWS]->(c) "
            "SET r.mastery = $mastery, r.last_reviewed = datetime()"
        )
        await self._client.execute_query(
            cypher_knows,
            {"user_id": user_id, "concept": concept, "mastery": mastery},
        )
        logger.info("concept_known", user_id=user_id, concept=concept, mastery=mastery)

    async def get_knowledge_map(self, user_id: int) -> list[KnowledgeNode]:
        """Return all concepts the user KNOWS with mastery levels."""
        cypher = (
            "MATCH (u:User {id: $user_id})-[r:KNOWS]->(c) "
            "RETURN c.name AS concept, r.mastery AS mastery, "
            "r.last_reviewed AS last_reviewed, c.aliases AS aliases"
        )
        rows = await self._client.execute_query(cypher, {"user_id": user_id})
        return [
            KnowledgeNode(
                concept=row["concept"],
                mastery=row["mastery"],
                last_reviewed=row.get("last_reviewed"),
                aliases=row.get("aliases") or [],
            )
            for row in rows
        ]

    async def get_knowledge_gaps(self, user_id: int, concept: str) -> list[KnowledgeGap]:
        """Find missing prerequisites for a given concept.

        A gap is a concept that is a PREREQUISITE_OF the target concept
        but the user does NOT KNOW (or mastery < 0.3).
        """
        cypher = (
            "MATCH (prereq:Concept)-[:PREREQUISITE_OF]->(target:Concept {name: $concept}) "
            "WHERE NOT EXISTS { "
            "  MATCH (u:User {id: $user_id})-[r:KNOWS]->(prereq) "
            "  WHERE r.mastery >= 0.3 "
            "} "
            "RETURN prereq.name AS concept, target.name AS required_by"
        )
        rows = await self._client.execute_query(cypher, {"user_id": user_id, "concept": concept})
        return [
            KnowledgeGap(concept=row["concept"], required_by=row["required_by"]) for row in rows
        ]

    async def update_mastery(self, user_id: int, concept: str, new_mastery: float) -> None:
        """Update mastery level for an existing KNOWS relationship."""
        new_mastery = _clamp(new_mastery)
        cypher = (
            "MATCH (u:User {id: $user_id})-[r:KNOWS]->(c:Concept {name: $concept}) "
            "SET r.mastery = $mastery, r.last_reviewed = datetime()"
        )
        await self._client.execute_query(
            cypher,
            {"user_id": user_id, "concept": concept, "mastery": new_mastery},
        )
        logger.info("mastery_updated", user_id=user_id, concept=concept, mastery=new_mastery)
