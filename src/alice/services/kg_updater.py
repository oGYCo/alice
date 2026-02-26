"""Knowledge Graph updater — processes user feedback and updates Neo4j knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, cast

import structlog

from alice.graph.client import GraphClient
from alice.graph.user_kg import UserKnowledgeGraph
from alice.llm.protocol import LLMClient


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def error(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

# Mastery delta constants
_POSITIVE_BOOST = 0.15
_INFERENTIAL_FACTOR = 0.5  # prerequisite boost = POSITIVE_BOOST * 0.5
_NEGATIVE_PENALTY = 0.1
_EXPLAIN_MASTERY = 0.1
_SEEN_MASTERY = 1.0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class KGUpdateResult:
    """Result returned by KGUpdater.update_on_feedback()."""

    user_id: int
    content_id: int
    feedback_type: str
    concepts_updated: list[str] = field(default_factory=list)
    mastery_changes: dict[str, float] = field(default_factory=dict)  # concept -> new mastery
    success: bool = True
    error: str | None = None


class KGUpdater:
    """Updates the user knowledge graph in Neo4j when the user gives feedback on content."""

    def __init__(self, graph_client: GraphClient, llm_client: LLMClient) -> None:
        self._client = graph_client
        self._llm = llm_client
        self._ukg = UserKnowledgeGraph(graph_client)

    async def update_on_feedback(
        self,
        user_id: int,
        content_id: int,
        feedback_type: str,
    ) -> KGUpdateResult:
        """Dispatch appropriate skill based on feedback type and return update result."""
        result = KGUpdateResult(
            user_id=user_id,
            content_id=content_id,
            feedback_type=feedback_type,
        )
        try:
            if feedback_type == "positive":
                await self._update_knowledge_graph(user_id, content_id, result)
            elif feedback_type == "seen":
                await self._calibrate_difficulty(user_id, content_id, result)
            elif feedback_type == "negative":
                await self._adjust_preferences(user_id, content_id, result)
            elif feedback_type == "explain_concept":
                await self._discover_interest(user_id, content_id, result)
            elif feedback_type == "save_for_later":
                # No KG change — just acknowledge
                pass
            else:
                logger.debug("unknown_feedback_type", feedback_type=feedback_type)

            logger.info(
                "kg_update_complete",
                user_id=user_id,
                content_id=content_id,
                feedback_type=feedback_type,
                concepts_updated=len(result.concepts_updated),
            )
        except Exception as exc:
            logger.error(
                "kg_update_failed",
                user_id=user_id,
                content_id=content_id,
                feedback_type=feedback_type,
                error=str(exc),
            )
            result.success = False
            result.error = str(exc)

        return result

    # ── Skill methods ─────────────────────────────────────────────────────────

    async def _update_knowledge_graph(
        self,
        user_id: int,
        content_id: int,
        result: KGUpdateResult,
    ) -> None:
        """Positive feedback: boost mastery +0.15, apply inferential boost to prerequisites."""
        concepts = await self._get_content_concepts(content_id)
        if not concepts:
            return

        for concept_name, current_mastery in concepts:
            new_mastery = _clamp(current_mastery + _POSITIVE_BOOST)
            await self._ukg.update_mastery(user_id, concept_name, new_mastery)
            result.concepts_updated.append(concept_name)
            result.mastery_changes[concept_name] = new_mastery

            # Inferential boost: prerequisites of the boosted concept
            prereqs = await self._get_prerequisites(concept_name)
            for prereq_name, prereq_mastery in prereqs:
                inferential_boost = _POSITIVE_BOOST * _INFERENTIAL_FACTOR
                new_prereq_mastery = _clamp(prereq_mastery + inferential_boost)
                await self._ukg.update_mastery(user_id, prereq_name, new_prereq_mastery)
                if prereq_name not in result.concepts_updated:
                    result.concepts_updated.append(prereq_name)
                result.mastery_changes[prereq_name] = new_prereq_mastery

    async def _calibrate_difficulty(
        self,
        user_id: int,
        content_id: int,
        result: KGUpdateResult,
    ) -> None:
        """Seen feedback: confirm mastery → 1.0 for all content concepts."""
        concepts = await self._get_content_concepts(content_id)
        if not concepts:
            return

        for concept_name, _ in concepts:
            await self._ukg.update_mastery(user_id, concept_name, _SEEN_MASTERY)
            result.concepts_updated.append(concept_name)
            result.mastery_changes[concept_name] = _SEEN_MASTERY

    async def _adjust_preferences(
        self,
        user_id: int,
        content_id: int,
        result: KGUpdateResult,
    ) -> None:
        """Negative feedback: reduce mastery -0.1, use LLM to analyse mismatch."""
        # Get content summary for LLM mismatch analysis
        summary_rows = await self._client.execute_query(
            "MATCH (c:Content {id: $content_id}) RETURN c.summary AS summary",
            {"content_id": content_id},
        )
        content_summary = summary_rows[0]["summary"] if summary_rows else ""

        concepts = await self._get_content_concepts(content_id)

        # LLM mismatch analysis (best-effort — don't fail if LLM errors)
        if content_summary:
            known_concepts = [c[0] for c in concepts] if concepts else []
            prompt = (
                f"Content summary: {content_summary}\n"
                f"User's known concepts: {known_concepts}\n"
                "Analyse why this content was rejected and identify the mismatch reason."
            )
            try:
                mismatch_reason = await self._llm.complete(prompt)
                logger.debug(
                    "mismatch_analysis",
                    user_id=user_id,
                    content_id=content_id,
                    reason=mismatch_reason[:200],
                )
            except Exception as llm_exc:
                logger.debug("mismatch_llm_failed", error=str(llm_exc))

        if not concepts:
            return

        for concept_name, current_mastery in concepts:
            new_mastery = _clamp(current_mastery - _NEGATIVE_PENALTY)
            await self._ukg.update_mastery(user_id, concept_name, new_mastery)
            result.concepts_updated.append(concept_name)
            result.mastery_changes[concept_name] = new_mastery

    async def _discover_interest(
        self,
        user_id: int,
        content_id: int,
        result: KGUpdateResult,
    ) -> None:
        """Explain concept feedback: record knowledge gap, set mastery → 0.1."""
        concepts = await self._get_content_concepts(content_id)
        if not concepts:
            return

        for concept_name, _ in concepts:
            await self._ukg.update_mastery(user_id, concept_name, _EXPLAIN_MASTERY)
            result.concepts_updated.append(concept_name)
            result.mastery_changes[concept_name] = _EXPLAIN_MASTERY

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _get_content_concepts(self, content_id: int) -> list[tuple[str, float]]:
        """Query Neo4j for concepts associated with a content item.

        Returns list of (concept_name, current_mastery) tuples.
        If content node doesn't exist, returns empty list.
        """
        rows = await self._client.execute_query(
            "MATCH (c:Content {id: $content_id})-[:DISCUSSES]->(concept) "
            "RETURN concept.name AS name, concept.mastery AS mastery",
            {"content_id": content_id},
        )
        return [
            (row["name"], float(row["mastery"]) if row["mastery"] is not None else 0.0)
            for row in rows
        ]

    async def _get_prerequisites(self, concept_name: str) -> list[tuple[str, float]]:
        """Return prerequisites of a concept with their current mastery values.

        Queries: (prereq)-[:PREREQUISITE_OF]->(concept).
        """
        rows = await self._client.execute_query(
            "MATCH (prereq:Concept)-[:PREREQUISITE_OF]->(c:Concept {name: $concept_name}) "
            "RETURN prereq.name AS prereq_name, prereq.mastery AS mastery",
            {"concept_name": concept_name},
        )
        return [
            (row["prereq_name"], float(row["mastery"]) if row["mastery"] is not None else 0.0)
            for row in rows
        ]
