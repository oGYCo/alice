"""GraphRAG Hybrid Query Engine — graph + full-text + semantic fusion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, cast

import structlog

from alice.graph.client import GraphClient
from alice.graph.user_kg import UserKnowledgeGraph
from alice.llm.protocol import LLMClient
from alice.services.search import SearchService


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def warning(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...
    def error(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))


# ---------------------------------------------------------------------------
# Configuration constants (can be wired into alice.config settings in production)
# ---------------------------------------------------------------------------

GRAPHRAG_GRAPH_WEIGHT: float = 0.5
GRAPHRAG_TEXT_WEIGHT: float = 0.3
GRAPHRAG_SEMANTIC_WEIGHT: float = 0.2

# Max concept hops when traversing graph
GRAPH_MAX_HOPS: int = 3

# Meilisearch result limit per query
TEXT_SEARCH_LIMIT: int = 20


# ---------------------------------------------------------------------------
# Query mode enum
# ---------------------------------------------------------------------------


class QueryMode(StrEnum):
    HYBRID = "hybrid"
    GRAPH_ONLY = "graph_only"
    TEXT_ONLY = "text_only"


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class GraphHit:
    """A content item found via graph traversal."""

    content_id: str
    score: float  # normalized 0.0–1.0
    matched_concepts: list[str] = field(default_factory=list)
    hop_distance: int = 0


@dataclass
class TextHit:
    """A content item found via full-text Meilisearch search."""

    content_id: str
    score: float  # Meilisearch ranking score normalized to 0.0–1.0
    highlights: dict[str, str] = field(default_factory=dict)


@dataclass
class SemanticHit:
    """A content item found via semantic (embedding) similarity."""

    content_id: str
    score: float  # cosine similarity 0.0–1.0


@dataclass
class RankedResult:
    """Final merged result from all retrieval modes."""

    content_id: str
    score: float  # weighted final score
    source: str  # "graph", "text", "semantic", or comma-separated when merged
    graph_score: float = 0.0
    text_score: float = 0.0
    semantic_score: float = 0.0

    def __repr__(self) -> str:
        return f"RankedResult(id={self.content_id}, score={self.score:.3f}, source={self.source})"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


class GraphRAGQueryEngine:
    """Unified query layer combining graph, full-text, and semantic retrieval.

    Weights (configurable):
      - Graph traversal: GRAPHRAG_GRAPH_WEIGHT (default 0.5)
      - Full-text search: GRAPHRAG_TEXT_WEIGHT (default 0.3)
      - Semantic matching: GRAPHRAG_SEMANTIC_WEIGHT (default 0.2, stub in Phase 2)

    Graceful degradation: if any backend is unavailable, remaining weights
    are redistributed proportionally.
    """

    def __init__(
        self,
        graph_client: GraphClient,
        search_service: SearchService,
        llm_client: LLMClient,
        graph_weight: float = GRAPHRAG_GRAPH_WEIGHT,
        text_weight: float = GRAPHRAG_TEXT_WEIGHT,
        semantic_weight: float = GRAPHRAG_SEMANTIC_WEIGHT,
    ) -> None:
        self._graph = graph_client
        self._search = search_service
        self._llm = llm_client
        self._user_kg = UserKnowledgeGraph(graph_client)
        self._graph_weight = graph_weight
        self._text_weight = text_weight
        self._semantic_weight = semantic_weight

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        text: str,
        user_id: int,
        mode: QueryMode = QueryMode.HYBRID,
        limit: int = 10,
    ) -> list[RankedResult]:
        """Execute a hybrid query and return ranked results.

        Args:
            text: Natural language query string.
            user_id: User ID for personalization via knowledge graph.
            mode: HYBRID (all sources), GRAPH_ONLY, or TEXT_ONLY.
            limit: Max number of results to return.

        Returns:
            Deduplicated, ranked list of RankedResult objects.
        """
        # Extract concepts from query text for graph traversal
        concepts = await self._extract_query_concepts(text)

        graph_hits: list[GraphHit] = []
        text_hits: list[TextHit] = []
        semantic_hits: list[SemanticHit] = []

        if mode in (QueryMode.HYBRID, QueryMode.GRAPH_ONLY):
            graph_hits = await self._graph_search(concepts, user_id)

        if mode in (QueryMode.HYBRID, QueryMode.TEXT_ONLY):
            rewritten = await self._rewrite_query(text)
            text_hits = await self._text_search(rewritten)

        if mode == QueryMode.HYBRID:
            # Phase 2 stub: semantic search always returns empty (no embeddings yet)
            semantic_hits = await self._semantic_search(text)

        results = self._merge_and_rank(
            graph_hits,
            text_hits,
            semantic_hits,
            mode=mode,
        )
        results = self._deduplicate(results)
        results.sort(key=lambda r: r.score, reverse=True)

        logger.info(
            "graphrag_query_complete",
            query=text[:80],
            user_id=user_id,
            results=len(results[:limit]),
            mode=mode.value,
        )
        return results[:limit]

    # ------------------------------------------------------------------
    # Internal retrieval methods
    # ------------------------------------------------------------------

    async def _graph_search(
        self,
        concepts: list[str],
        user_id: int,
    ) -> list[GraphHit]:
        """Query Neo4j for content related to concepts within N hops.

        Strategy:
        1. Get the user's known concepts for context.
        2. For each query concept, find Content nodes reachable via concept graph.
        3. Score by hop distance: closer = higher score.
        """
        if not concepts:
            return []

        try:
            # Find Content nodes connected to any of the query concepts within MAX_HOPS
            cypher = (
                "UNWIND $concepts AS concept_name "
                "MATCH (c:Concept {name: concept_name})<-[:DISCUSSES|EXTENDS|APPLIES_TO*1.."
                + str(GRAPH_MAX_HOPS)
                + "]-(content:Content) "
                "RETURN content.id AS content_id, "
                "min(length(shortestPath((content)-[*]-(c)))) AS min_dist "
                "ORDER BY min_dist ASC LIMIT 50"
            )
            rows = await self._graph.execute_query(cypher, {"concepts": concepts})

            hits: list[GraphHit] = []
            for row in rows:
                dist = int(row.get("min_dist", GRAPH_MAX_HOPS))
                # Score: 1/(1+d) so d=0→1.0, d=1→0.5, d=2→0.33
                score = 1.0 / (1.0 + dist)
                hits.append(
                    GraphHit(
                        content_id=str(row["content_id"]),
                        score=score,
                        matched_concepts=concepts,
                        hop_distance=dist,
                    )
                )
            return hits

        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_search_failed", error=str(exc))
            return []

    async def _text_search(self, query: str) -> list[TextHit]:
        """Query Meilisearch with the (rewritten) query string."""
        try:
            result = self._search.search(query, limit=TEXT_SEARCH_LIMIT)
            hits_raw = result.get("hits", [])

            hits: list[TextHit] = []
            for i, hit in enumerate(hits_raw):
                # Normalize rank position to 0.0–1.0 (top result = 1.0)
                score = 1.0 - (i / max(len(hits_raw), 1))
                formatted = hit.get("_formatted", {})
                hits.append(
                    TextHit(
                        content_id=str(hit["id"]),
                        score=score,
                        highlights={
                            "title": formatted.get("title", ""),
                            "summary": formatted.get("summary", ""),
                        },
                    )
                )
            return hits

        except Exception as exc:  # noqa: BLE001
            logger.warning("text_search_failed", error=str(exc))
            return []

    async def _semantic_search(self, _query: str) -> list[SemanticHit]:
        """Phase 2 stub — no embeddings on Content model yet.

        Phase 3 will add embedding JSONB column to Content and implement
        cosine similarity search here.
        """
        return []

    # ------------------------------------------------------------------
    # Query preprocessing
    # ------------------------------------------------------------------

    async def _extract_query_concepts(self, text: str) -> list[str]:
        """Extract concept names from natural language query text.

        Uses LLM for concept extraction. Falls back to splitting on spaces
        if LLM call fails (graceful degradation).
        """
        try:
            prompt = (
                "Extract the key technical concepts from this query as a "
                "JSON array of snake_case strings. Return ONLY the JSON array, "
                "no explanation.\n\nQuery: " + text
            )
            response = await self._llm.complete(
                prompt, system="You are a concept extraction assistant."
            )
            # Parse first JSON array from response
            import json  # noqa: PLC0415

            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                concepts = json.loads(response[start:end])
                if isinstance(concepts, list):
                    return [str(c) for c in concepts[:10]]
        except Exception as exc:  # noqa: BLE001
            logger.warning("concept_extraction_failed", error=str(exc))

        # Fallback: use cleaned words from query as concepts
        import re  # noqa: PLC0415

        words = re.findall(r"\w+", text.lower())
        return [w for w in words if len(w) > 3][:8]

    async def _rewrite_query(self, text: str) -> str:
        """Rewrite query for better full-text search using LLM.

        Expands user query into search-friendly terms.
        Falls back to original query if LLM call fails.
        """
        try:
            prompt = (
                "Rewrite this search query to improve full-text search results. "
                "Return only the rewritten query, no explanation.\n\nQuery: " + text
            )
            rewritten = await self._llm.complete(
                prompt, system="You are a search query optimization assistant."
            )
            return rewritten.strip() or text
        except Exception as exc:  # noqa: BLE001
            logger.warning("query_rewrite_failed", error=str(exc))
            return text

    # ------------------------------------------------------------------
    # Merging and deduplication
    # ------------------------------------------------------------------

    def _merge_and_rank(
        self,
        graph_hits: list[GraphHit],
        text_hits: list[TextHit],
        semantic_hits: list[SemanticHit],
        mode: QueryMode = QueryMode.HYBRID,
    ) -> list[RankedResult]:
        """Merge hits from all sources using configurable weights.

        When a backend has no results, redistributes its weight proportionally
        to remaining backends (graceful degradation).
        """
        # Determine effective weights based on which backends returned results
        gw = self._graph_weight if graph_hits else 0.0
        tw = self._text_weight if text_hits else 0.0
        sw = self._semantic_weight if semantic_hits else 0.0

        total = gw + tw + sw
        if total == 0.0:
            return []

        # Normalize weights
        gw /= total
        tw /= total
        sw /= total

        # Build per-content_id score accumulators
        scores: dict[str, dict[str, float]] = {}

        for hit in graph_hits:
            s = scores.setdefault(hit.content_id, {"g": 0.0, "t": 0.0, "s": 0.0})
            s["g"] = max(s["g"], hit.score)

        for hit in text_hits:
            s = scores.setdefault(hit.content_id, {"g": 0.0, "t": 0.0, "s": 0.0})
            s["t"] = max(s["t"], hit.score)

        for hit in semantic_hits:
            s = scores.setdefault(hit.content_id, {"g": 0.0, "t": 0.0, "s": 0.0})
            s["s"] = max(s["s"], hit.score)

        results: list[RankedResult] = []
        for content_id, s in scores.items():
            final_score = gw * s["g"] + tw * s["t"] + sw * s["s"]
            # Determine source label
            source_parts = []
            if s["g"] > 0:
                source_parts.append("graph")
            if s["t"] > 0:
                source_parts.append("text")
            if s["s"] > 0:
                source_parts.append("semantic")
            results.append(
                RankedResult(
                    content_id=content_id,
                    score=final_score,
                    source=",".join(source_parts) if source_parts else "unknown",
                    graph_score=s["g"],
                    text_score=s["t"],
                    semantic_score=s["s"],
                )
            )
        return results

    def _deduplicate(self, results: list[RankedResult]) -> list[RankedResult]:
        """Remove duplicate content_ids, keeping highest score."""
        seen: dict[str, RankedResult] = {}
        for r in results:
            if r.content_id not in seen or r.score > seen[r.content_id].score:
                seen[r.content_id] = r
        return list(seen.values())
