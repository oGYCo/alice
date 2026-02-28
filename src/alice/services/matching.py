"""Content-User Matching Algorithm — computes Match_score for ranking relevance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

import structlog

from alice.graph.client import GraphClient
from alice.graph.extractor import ContentSubgraph
from alice.graph.user_kg import UserKnowledgeGraph
from alice.services.memory_system import MemoryContext, MemoryManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
from alice.services.search import SearchService


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

# Default recommendation threshold
DEFAULT_RECOMMEND_THRESHOLD = 0.4

# Component weights for Match_score
WEIGHT_PREREQUISITE = 0.5
WEIGHT_DISTANCE = 0.3
WEIGHT_DIFFICULTY = 0.2

# Mastery threshold for "knows" prerequisite
MASTERY_THRESHOLD = 0.3

# Max graph hops to search for concept proximity (Cypher query)
MAX_HOPS = 4


class MatchResult:
    """Result of a matching computation with sub-scores."""

    def __init__(
        self,
        match_score: float,
        prerequisite_coverage: float,
        concept_distance_fit: float,
        difficulty_fit: float,
        should_defer: bool,
    ) -> None:
        self.match_score = match_score
        self.prerequisite_coverage = prerequisite_coverage
        self.concept_distance_fit = concept_distance_fit
        self.difficulty_fit = difficulty_fit
        self.should_defer = should_defer

    def __repr__(self) -> str:
        return (
            f"MatchResult(score={self.match_score:.3f}, "
            f"prereq={self.prerequisite_coverage:.3f}, "
            f"dist={self.concept_distance_fit:.3f}, "
            f"diff={self.difficulty_fit:.3f}, "
            f"defer={self.should_defer})"
        )


class MatchingService:
    """Computes Match_score = 0.5·Prerequisite_coverage + 0.3·Concept_distance_fit + 0.2·Difficulty_fit.

    Integrates with RankingService as R_relevance.

    Components:
    - Prerequisite_coverage: fraction of content entry_concepts where user mastery >= 0.3
    - Concept_distance_fit: how close content concepts are to user's known concepts in graph
    - Difficulty_fit: 1 - |content.difficulty - user_average_mastery|
    """

    def __init__(
        self,
        client: GraphClient,
        recommend_threshold: float = DEFAULT_RECOMMEND_THRESHOLD,
        search_service: SearchService | None = None,
    ) -> None:
        self._client = client
        self._user_kg = UserKnowledgeGraph(client)
        self._threshold = recommend_threshold
        self._search_service = search_service

    async def compute_match_score(
        self,
        user_id: int,
        subgraph: ContentSubgraph,
    ) -> MatchResult:
        """Compute Match_score for a given user × content subgraph pair."""
        # Fetch user knowledge once
        known_concepts = await self._user_kg.get_knowledge_map(user_id)
        mastery_map: dict[str, float] = {kn.concept: kn.mastery for kn in known_concepts}

        prereq = self._compute_prerequisite_coverage(subgraph, mastery_map)
        dist = await self._compute_concept_distance_fit(subgraph, mastery_map)
        diff = self._compute_difficulty_fit(subgraph, mastery_map)

        match_score = (
            WEIGHT_PREREQUISITE * prereq + WEIGHT_DISTANCE * dist + WEIGHT_DIFFICULTY * diff
        )
        # Clamp to [0.0, 1.0]
        match_score = max(0.0, min(1.0, match_score))

        result = MatchResult(
            match_score=match_score,
            prerequisite_coverage=prereq,
            concept_distance_fit=dist,
            difficulty_fit=diff,
            should_defer=match_score < self._threshold,
        )
        logger.info(
            "match_score_computed",
            user_id=user_id,
            match_score=round(match_score, 4),
            should_defer=result.should_defer,
        )
        return result

    # ------------------------------------------------------------------
    # Sub-score implementations
    # ------------------------------------------------------------------

    def _compute_prerequisite_coverage(
        self,
        subgraph: ContentSubgraph,
        mastery_map: dict[str, float],
    ) -> float:
        """Fraction of entry_concepts where user mastery >= MASTERY_THRESHOLD.

        If no entry concepts, assume fully accessible → returns 1.0.
        """
        if not subgraph.entry_concepts:
            return 1.0
        covered = sum(
            1
            for concept in subgraph.entry_concepts
            if mastery_map.get(concept, 0.0) >= MASTERY_THRESHOLD
        )
        return covered / len(subgraph.entry_concepts)

    async def _compute_concept_distance_fit(
        self,
        subgraph: ContentSubgraph,
        mastery_map: dict[str, float],
    ) -> float:
        """How reachable are content concepts from user's known concepts in the graph?

        Uses Neo4j shortest-path query. For each content concept not already known
        by the user, find the shortest path length from any known concept.

        Score = 1 / (1 + average_min_distance)

        If user knows ALL content concepts already → 1.0 (perfect fit — refresher).
        If no known concepts → 0.0 (user has no foothold).
        """
        content_concept_names = [n.name for n in subgraph.nodes]
        if not content_concept_names:
            return 0.5  # neutral when no concepts extracted

        known_names = list(mastery_map.keys())
        if not known_names:
            return 0.0  # user has no knowledge at all

        # Concepts the user already knows directly
        already_known = [c for c in content_concept_names if c in mastery_map]
        unknown_in_content = [c for c in content_concept_names if c not in mastery_map]

        if not unknown_in_content:
            # User knows everything in the content — great refresher
            return 1.0

        # Query shortest path distances from ANY known concept to each unknown content concept
        distances: list[float] = []
        for target in unknown_in_content:
            dist = await self._query_shortest_distance(known_names, target)
            distances.append(dist)

        avg_dist = sum(distances) / len(distances) if distances else 0.0

        # Score: closer = higher. 1/(1+d): d=0→1.0, d=1→0.5, d=2→0.33, d=∞→0
        score = 1.0 / (1.0 + avg_dist)

        # Blend with direct-knowledge ratio for smoother behavior
        known_ratio = len(already_known) / len(content_concept_names)
        blended = 0.5 * score + 0.5 * known_ratio
        return max(0.0, min(1.0, blended))

    def _compute_difficulty_fit(
        self,
        subgraph: ContentSubgraph,
        mastery_map: dict[str, float],
    ) -> float:
        """Difficulty fit = 1 - |content_difficulty - user_average_mastery|.

        If user has no known concepts, defaults to 0.5 average mastery.
        Result clamped to [0.0, 1.0].
        """
        user_avg = sum(mastery_map.values()) / len(mastery_map) if mastery_map else 0.5
        diff = abs(subgraph.difficulty - user_avg)
        return max(0.0, min(1.0, 1.0 - diff))

    async def _query_shortest_distance(
        self,
        known_names: list[str],
        target: str,
    ) -> float:
        """Query Neo4j for shortest path length from any known concept to target.

        Returns MAX_HOPS + 1 (unreachable sentinel) if no path found within MAX_HOPS.
        """
        # Use MATCH with variable-length path, limited to MAX_HOPS
        cypher = (
            "MATCH (src:Concept), (tgt:Concept {name: $target}) "
            "WHERE src.name IN $known_names "
            f"AND src.name <> $target "
            f"MATCH p = shortestPath((src)-[*1..{MAX_HOPS}]-(tgt)) "
            "RETURN length(p) AS dist "
            "ORDER BY dist ASC LIMIT 1"
        )
        try:
            rows = await self._client.execute_query(
                cypher, {"known_names": known_names, "target": target}
            )
            if rows:
                return float(rows[0]["dist"])
        except Exception:  # noqa: BLE001
            # If graph query fails (Neo4j down, concept not in graph), treat as far away
            pass
        # Sentinel: not reachable within MAX_HOPS
        return float(MAX_HOPS + 1)

    # ------------------------------------------------------------------
    # Full R_relevance formula (for integration with RankingService)
    # ------------------------------------------------------------------

    async def compute_r_relevance(
        self,
        user_id: int,
        subgraph: ContentSubgraph,
        content_id: int | None = None,
        session: AsyncSession | None = None,
    ) -> float:
        """Full R_relevance = α·KG_match + β·Text_relevance + γ·Working_match + δ·Gap_fill.

        Components:
          - KG_match = Match_score from this service (α=0.6)
          - Text_relevance = Meilisearch text similarity (β=0.1)
          - Working_match = overlap between content concepts and user's
            working memory topics via MemoryManager (γ=0.1)
          - Gap_fill from get_knowledge_gaps (δ=0.2 bonus when gaps exist)

        When *session* is provided, working memory context is fetched from
        the database; otherwise falls back to a neutral 0.5.
        """
        result = await self.compute_match_score(user_id, subgraph)
        kg_match = result.match_score

        # Text-based relevance via Meilisearch
        known_concepts = await self._user_kg.get_knowledge_map(user_id)
        mastery_map: dict[str, float] = {kn.concept: kn.mastery for kn in known_concepts}
        text_relevance = await self._compute_text_relevance(content_id, mastery_map)

        # Working memory: use real memory context when session available
        if session is not None:
            memory_mgr = MemoryManager()
            memory_ctx = await memory_mgr.get_memory_context(session, user_id)
            working_match = self._compute_working_memory_match(subgraph, memory_ctx)
        else:
            working_match = 0.5  # neutral fallback when no DB session

        # Gap fill bonus: content has entry concepts user doesn't know but can reach
        gap_fill = await self._compute_gap_fill_bonus(user_id, subgraph)

        # Weights: α=0.6, β=0.1, γ=0.1, δ=0.2
        r_relevance = 0.6 * kg_match + 0.1 * text_relevance + 0.1 * working_match + 0.2 * gap_fill
        return max(0.0, min(1.0, r_relevance))

    def _compute_working_memory_match(
        self,
        subgraph: ContentSubgraph,
        memory_ctx: MemoryContext,
    ) -> float:
        """Score content relevance to the user's working memory topics.

        Returns the fraction of content concept nodes whose name overlaps
        (exact or substring, case-insensitive) with a working memory topic.
        When the user has no working topics or the content has no concept
        nodes, returns 0.5 (neutral).
        """
        if not memory_ctx.working_topics:
            return 0.5

        content_concepts = {n.name.lower() for n in subgraph.nodes}
        if not content_concepts:
            return 0.5

        working_lower = {t.lower() for t in memory_ctx.working_topics}

        matches = 0
        for concept in content_concepts:
            for topic in working_lower:
                if concept == topic or topic in concept or concept in topic:
                    matches += 1
                    break

        return matches / len(content_concepts)

    async def _compute_text_relevance(
        self,
        content_id: int | None,
        mastery_map: dict[str, float],
    ) -> float:
        """Compute text-based relevance using Meilisearch full-text search.

        Searches Meilisearch with the user's top known concepts and checks
        whether the target content appears in the results.  Higher rank in
        the result list → higher relevance score.

        Returns 0.5 (neutral) when search_service is not available or
        content_id is not provided.
        """
        if self._search_service is None or content_id is None:
            return 0.5

        if not mastery_map:
            return 0.0

        # Use top concepts by mastery as the search query
        top_concepts = sorted(mastery_map.items(), key=lambda x: x[1], reverse=True)[:5]
        query = " ".join(name.replace("_", " ") for name, _ in top_concepts)

        try:
            result = self._search_service.search(query, limit=20)
            hits = result.get("hits", [])
            content_id_str = str(content_id)
            for i, hit in enumerate(hits):
                if str(hit.get("id")) == content_id_str:
                    # Found — score based on rank position: top = 1.0, bottom ≈ 0.05
                    return 1.0 - (i / max(len(hits), 1))
            # Content not in results → low text relevance
            return 0.1
        except Exception:  # noqa: BLE001
            logger.debug("text_relevance_search_failed", content_id=content_id)
            return 0.5

    async def _compute_gap_fill_bonus(
        self,
        user_id: int,
        subgraph: ContentSubgraph,
    ) -> float:
        """Compute gap-fill bonus: fraction of entry concepts that are gaps user CAN fill.

        A concept is a fillable gap if:
        - user mastery < MASTERY_THRESHOLD (it's a gap)
        - AND content explains it (it's in entry_concepts)
        """
        if not subgraph.entry_concepts:
            return 0.0
        known_concepts = await self._user_kg.get_knowledge_map(user_id)
        mastery_map = {kn.concept: kn.mastery for kn in known_concepts}
        gaps = [c for c in subgraph.entry_concepts if mastery_map.get(c, 0.0) < MASTERY_THRESHOLD]
        return len(gaps) / len(subgraph.entry_concepts)
