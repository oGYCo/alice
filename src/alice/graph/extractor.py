"""Content subgraph extractor — uses LLM to extract concept graph from content."""

from __future__ import annotations

from typing import Protocol, cast

import structlog
from pydantic import BaseModel, Field

from alice.graph.repository import GraphRepository
from alice.graph.schema import NodeLabel, RelType
from alice.llm.protocol import LLMClient
from alice.prompts import PromptManager


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...
    def error(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


class ContentSubgraphNode(BaseModel):
    """A concept node extracted from content."""

    name: str  # English canonical name, snake_case
    type: str  # "concept" | "method" | "tool" | "theory"
    aliases: list[str] = []


class ContentSubgraphEdge(BaseModel):
    """A relationship edge between two concept nodes."""

    from_: str = Field(alias="from")  # source node name
    to: str
    relation: str  # "prerequisite" | "extends" | "applies_to" | "contrasts"

    model_config = {"populate_by_name": True}


class ContentSubgraph(BaseModel):
    """Structured concept graph extracted from a content item."""

    nodes: list[ContentSubgraphNode]
    edges: list[ContentSubgraphEdge]
    difficulty: float  # 0.0 to 1.0
    entry_concepts: list[str]


# Mapping helpers
_RELATION_MAP: dict[str, str] = {
    "prerequisite": RelType.PREREQUISITE_OF,
    "extends": RelType.EXTENDS,
    "applies_to": RelType.APPLIES_TO,
    "contrasts": RelType.CONTRASTS,
}

_TYPE_MAP: dict[str, str] = {
    "concept": NodeLabel.CONCEPT,
    "method": NodeLabel.METHOD,
    "tool": NodeLabel.TOOL,
    "theory": NodeLabel.THEORY,
}


class SubgraphExtractor:
    """Extracts a concept subgraph from content using DeepSeek LLM, stores in Neo4j."""

    def __init__(self, llm: LLMClient, graph_repo: GraphRepository) -> None:
        self._llm = llm
        self._graph_repo = graph_repo
        self._prompt_manager = PromptManager()

    async def extract(
        self,
        content_id: int,
        title: str,
        summary: str,
        key_points: list[str],
    ) -> ContentSubgraph:
        """Extract subgraph from content summary + key_points, store in Neo4j."""
        subgraph = await self._call_llm(title, summary, key_points)
        # Clamp difficulty to [0.0, 1.0]
        subgraph.difficulty = max(0.0, min(1.0, subgraph.difficulty))
        # Enforce max 10 nodes
        if len(subgraph.nodes) > 10:
            subgraph.nodes = subgraph.nodes[:10]
        await self._store_in_graph(content_id, subgraph)
        logger.info(
            "subgraph_extracted",
            content_id=content_id,
            nodes=len(subgraph.nodes),
            edges=len(subgraph.edges),
            difficulty=subgraph.difficulty,
        )
        return subgraph

    async def _call_llm(
        self,
        title: str,
        summary: str,
        key_points: list[str],
    ) -> ContentSubgraph:
        """Render prompt template, call LLM, parse into ContentSubgraph."""
        prompt = self._prompt_manager.render(
            "extract_subgraph",
            title=title,
            summary=summary,
            key_points=key_points,
        )
        return await self._llm.complete_structured(
            prompt,
            ContentSubgraph,
            system="You are a knowledge graph extraction expert. Return only valid JSON.",
        )

    async def _store_in_graph(
        self,
        content_id: int,
        subgraph: ContentSubgraph,
    ) -> None:
        """Upsert concept nodes + relationships into Neo4j."""
        # Build a name → label lookup for edge creation
        name_to_label: dict[str, str] = {}
        for node in subgraph.nodes:
            label = self._map_type_to_label(node.type)
            name_to_label[node.name] = label
            await self._graph_repo.upsert_concept(node.name, label=label, aliases=node.aliases)
            # Link content → concept
            await self._graph_repo.create_relationship(
                str(content_id),
                NodeLabel.CONTENT,
                node.name,
                label,
                RelType.DISCUSSES,
            )

        for edge in subgraph.edges:
            from_label = name_to_label.get(edge.from_, NodeLabel.CONCEPT)
            to_label = name_to_label.get(edge.to, NodeLabel.CONCEPT)
            rel = self._map_relation_to_reltype(edge.relation)
            await self._graph_repo.create_relationship(
                edge.from_,
                from_label,
                edge.to,
                to_label,
                rel,
            )

    def _map_relation_to_reltype(self, relation: str) -> str:
        """Map relation string → RelType constant."""
        return _RELATION_MAP.get(relation, RelType.EXTENDS)

    def _map_type_to_label(self, node_type: str) -> str:
        """Map node type string → NodeLabel constant."""
        return _TYPE_MAP.get(node_type, NodeLabel.CONCEPT)
