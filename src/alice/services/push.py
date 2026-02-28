"""Push service — fetch indexed content, format cards, deliver via Telegram bot."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.bot.handlers.push import send_push
from alice.graph.client import GraphClient
from alice.graph.extractor import ContentSubgraph, ContentSubgraphEdge, ContentSubgraphNode
from alice.graph.repository import GraphRepository
from alice.graph.user_kg import UserKnowledgeGraph
from alice.llm.protocol import LLMClient
from alice.models.content import Content, PipelineStatus
from alice.prompts import PromptManager
from alice.prompts import prompt_manager as _default_pm
from alice.schemas.content import ContentResponseSchema
from alice.services.graphrag_query import GraphRAGQueryEngine
from alice.services.matching import MatchingService
from alice.services.push_scheduler import PushScheduler
from alice.services.ranking import RankingService
from alice.services.search import SearchService
from alice.services.user_state import UserStateManager

logger = structlog.get_logger(__name__)


class PushService:
    """Service for fetching, formatting, and delivering pushed content."""

    def __init__(self, pm: PromptManager | None = None) -> None:
        self._pm = pm or _default_pm

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_next_push_batch(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 5,
        graph_client: GraphClient | None = None,
        content_type_filter: str | None = None,
        search_service: SearchService | None = None,
        llm_client: LLMClient | None = None,
    ) -> list[Content]:
        """Return up to ``limit`` indexed, unpushed content items ranked by P_score.

        When *graph_client* is provided the batch is personalised: more
        candidates are fetched, ``MatchingService`` computes per-user
        ``r_relevance``, ``RankingService`` recomputes ``p_score``, and the
        top-N results are returned.  When *graph_client* is ``None`` the
        pre-computed ``p_score`` ordering (falling back to ``quality_score``)
        is used directly.

        *content_type_filter* narrows candidates to those whose
        ``metadata_["content_type"]`` matches (ignored when ``"any"`` or
        ``None``).
        """
        push_scheduler = PushScheduler()
        now = datetime.now(UTC)
        t_timing = push_scheduler.get_timing_score(now)

        candidate_limit = limit * 3 if graph_client else limit
        result = await session.execute(
            select(Content)
            .where(
                Content.pipeline_status == PipelineStatus.indexed,
                Content.pushed_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(Content.p_score.desc().nullslast(), Content.quality_score.desc())  # type: ignore[union-attr]
            .limit(candidate_limit)
        )
        candidates = list(result.scalars().all())

        # Apply content-type filter when a specific window is requested
        if content_type_filter and content_type_filter != "any":
            candidates = [
                c
                for c in candidates
                if (c.metadata_ or {}).get("content_type") == content_type_filter
            ] or candidates  # fall back to unfiltered if none match

        if not candidates or graph_client is None:
            return candidates[:limit]

        # --- GraphRAG candidate discovery ---
        # Use the user's known concepts to find semantically related content
        # that may not appear in the top p_score ordering.
        if search_service and llm_client:
            try:
                user_kg = UserKnowledgeGraph(graph_client)
                known = await user_kg.get_knowledge_map(user_id)
                if known:
                    top_concepts = sorted(
                        known, key=lambda k: k.mastery, reverse=True
                    )[:5]
                    query_text = " ".join(
                        k.concept.replace("_", " ") for k in top_concepts
                    )
                    engine = GraphRAGQueryEngine(
                        graph_client=graph_client,
                        search_service=search_service,
                        llm_client=llm_client,
                    )
                    graphrag_results = await engine.query(
                        text=query_text, user_id=user_id, limit=limit * 2
                    )
                    existing_ids = {c.id for c in candidates}
                    extra_ids: list[int] = []
                    for r in graphrag_results:
                        try:
                            cid = int(r.content_id)
                            if cid not in existing_ids:
                                extra_ids.append(cid)
                        except (ValueError, TypeError):
                            continue
                    if extra_ids:
                        extra_result = await session.execute(
                            select(Content).where(
                                Content.id.in_(extra_ids),
                                Content.pipeline_status == PipelineStatus.indexed,
                                Content.pushed_at.is_(None),  # type: ignore[union-attr]
                            )
                        )
                        candidates.extend(list(extra_result.scalars().all()))
            except Exception:  # noqa: BLE001
                logger.warning(
                    "graphrag_candidate_discovery_failed",
                    user_id=user_id,
                    exc_info=True,
                )

        # Personalise with user-specific matching scores
        matching_svc = MatchingService(graph_client, search_service=search_service)
        ranking_svc = RankingService()

        # Apply user-mode push modifiers (daily/project/explore/low_energy)
        user_state_mgr = UserStateManager()
        push_mods = user_state_mgr.get_push_modifiers(user_id)

        scored: list[tuple[Content, float]] = []
        for content in candidates:
            subgraph = await self._reconstruct_subgraph(graph_client, content.id)
            if subgraph:
                r_relevance = await matching_svc.compute_r_relevance(
                    user_id, subgraph, content_id=content.id, session=session
                )
            else:
                r_relevance = 1.0
            p = ranking_svc.compute_p_score(
                content,
                r_relevance=r_relevance,
                t_timing=t_timing,
                user_mode_multiplier=push_mods.relevance_multiplier,
            )
            scored.append((content, p))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    # ------------------------------------------------------------------
    # Subgraph reconstruction helpers
    # ------------------------------------------------------------------

    async def _reconstruct_subgraph(
        self,
        graph_client: GraphClient,
        content_id: int,
    ) -> ContentSubgraph | None:
        """Reconstruct a ``ContentSubgraph`` from Neo4j for matching."""
        try:
            repo = GraphRepository(graph_client)
            data = await repo.get_content_subgraph(content_id)
            if not data["nodes"]:
                return None

            # Retrieve difficulty stored on Content node (set during graph extraction)
            rows = await graph_client.execute_query(
                "MATCH (c:Content {id: $cid}) RETURN c.difficulty AS diff",
                {"cid": content_id},
            )
            difficulty = (
                float(rows[0]["diff"])
                if rows and rows[0].get("diff") is not None
                else 0.5
            )

            nodes = [
                ContentSubgraphNode(
                    name=n["name"],
                    type=n.get("label", "Concept").lower(),
                )
                for n in data["nodes"]
            ]
            edges = [
                ContentSubgraphEdge(
                    **{"from": e["from"], "to": e["to"], "relation": e["relation"]}
                )
                for e in data["edges"]
            ]

            # entry_concepts: nodes not targeted by prerequisite edges
            prereq_targets = {
                e["to"]
                for e in data["edges"]
                if e.get("relation") == "prerequisite_of"
            }
            entry_concepts = [
                n["name"] for n in data["nodes"] if n["name"] not in prereq_targets
            ]

            return ContentSubgraph(
                nodes=nodes,
                edges=edges,
                difficulty=difficulty,
                entry_concepts=entry_concepts or [n["name"] for n in data["nodes"]],
            )
        except Exception:
            logger.warning("subgraph_reconstruct_failed", content_id=content_id, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_push_card(self, content: Content) -> str:
        """Render the push_card.j2 Jinja2 template for the given content.

        Returns a Markdown-formatted string suitable for Telegram.
        """
        return self._pm.render(
            "push_card",
            title=content.title,
            summary=content.summary,
            key_points=content.key_points,
            source_url=content.source_url,
            estimated_read_time=content.estimated_read_time,
        )

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    async def deliver_push(
        self,
        *,
        bot: Bot,
        user_id: int,
        chat_id: int,
        content_list: list[Content],
        session: AsyncSession,
    ) -> None:
        """Deliver push cards to a Telegram user and record timestamps.

        For each content item:
        1. Build a ContentResponseSchema (required by send_push)
        2. Call send_push() to deliver the card
        3. Set content.pushed_at = now(UTC) to mark as delivered

        Commits once after all deliveries.
        """
        if not content_list:
            return

        now = datetime.now(UTC)

        for content in content_list:
            schema = ContentResponseSchema.model_validate(content)
            await send_push(bot=bot, chat_id=chat_id, content=schema)
            content.pushed_at = now

        await session.commit()
