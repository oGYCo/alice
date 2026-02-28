"""Pipeline Celery task definitions.

IMPORTANT: These are individual tasks — NO Celery chains.
Each task reads/writes pipeline_status to PostgreSQL via ContentStorageService.
On success: dispatches the next task manually via .delay().
On failure: sets status=failed with structured error JSON.

Tasks are sync (Celery workers are synchronous), but services are async.
We bridge this with asyncio.run() inside each task.
"""

from __future__ import annotations

import asyncio
import json
import logging

from alice.db import AsyncSessionLocal
from alice.graph.client import GraphClient
from alice.graph.extractor import SubgraphExtractor
from alice.graph.repository import GraphRepository
from alice.llm.factory import create_llm_client
from alice.models.content import PipelineStatus
from alice.services.gatekeeper import GatekeeperService
from alice.services.scoring import ScoringService
from alice.services.storage import ContentStorageService
from alice.services.understanding import UnderstandingService
from alice.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_storage(session) -> ContentStorageService:
    return ContentStorageService(session)


def _create_graph_client() -> GraphClient:
    """Build a GraphClient from env-configured NEO4J_URI / NEO4J_AUTH."""
    from alice.config import settings
    user, password = settings.NEO4J_AUTH.split("/", 1)
    return GraphClient(settings.NEO4J_URI, (user, password))


async def _fail_content(session, content_id: int, stage: str, reason: str) -> None:
    """Mark content as failed with structured error JSON in DB."""
    storage = ContentStorageService(session)
    error_json = json.dumps({"failure_reason": reason, "failed_at_stage": stage})
    await storage.update_pipeline_status(content_id, PipelineStatus.failed, error=error_json)


# ---------------------------------------------------------------------------
# Stage 1: Gatekeeper
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_gatekeeper",
    max_retries=3,
    retry_backoff=True,
)
def task_run_gatekeeper(self, content_id: int) -> dict:
    """Stage 1: Run gatekeeper filter.

    Reads:  content.pipeline_status == 'fetched'
    Writes: content.pipeline_status = 'gatekept' OR 'failed'
    Next:   task_run_understanding (if passed)
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            # Gatekeeper uses Ollama with automatic rule-based fallback
            llm_client = create_llm_client("ollama")
            gk = GatekeeperService(llm_client)

            text = content.extracted_text or content.raw_text or ""
            url = content.source_url or ""

            try:
                decision = await gk.evaluate(text, url)
            except Exception as exc:
                logger.error(
                    "gatekeeper_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                raise self.retry(exc=exc)

            if decision.passed:
                await storage.update_pipeline_status(content_id, PipelineStatus.gatekept)
                # Dispatch next stage — NO Celery chain
                task_run_understanding.delay(content_id)
                logger.info(
                    "gatekeeper_passed",
                    extra={"content_id": content_id, "method": decision.method},
                )
                return {
                    "content_id": content_id,
                    "stage": "gatekeeper",
                    "passed": True,
                }
            else:
                error_json = json.dumps(
                    {
                        "failure_reason": decision.reason,
                        "failed_at_stage": "gatekeeper",
                    }
                )
                await storage.update_pipeline_status(
                    content_id, PipelineStatus.failed, error=error_json
                )
                logger.info(
                    "gatekeeper_rejected",
                    extra={
                        "content_id": content_id,
                        "reason": decision.reason,
                    },
                )
                return {
                    "content_id": content_id,
                    "stage": "gatekeeper",
                    "passed": False,
                    "reason": decision.reason,
                }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 2: Understanding
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_understanding",
    max_retries=3,
    retry_backoff=True,
)
def task_run_understanding(self, content_id: int) -> dict:
    """Stage 2: Run content understanding (DeepSeek).

    Reads:  content.pipeline_status == 'gatekept'
    Writes: summary, key_points, domains, estimated_read_time + status='understood'
    Next:   task_run_scoring
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            llm_client = create_llm_client("deepseek")
            understanding_svc = UnderstandingService(llm_client)

            title = content.title or ""
            text = content.extracted_text or content.raw_text or ""
            language = content.language or "en"

            try:
                result = await understanding_svc.process(title, text, language)
            except Exception as exc:
                logger.error(
                    "understanding_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                error_json = json.dumps(
                    {
                        "failure_reason": str(exc),
                        "failed_at_stage": "understanding",
                    }
                )
                await storage.update_pipeline_status(
                    content_id, PipelineStatus.failed, error=error_json
                )
                raise self.retry(exc=exc)

            await storage.update_understanding(
                content_id,
                summary=result.summary,
                key_points=result.key_points,
                domains=result.domains,
                read_time=result.estimated_read_time,
                content_type=result.content_type,
            )
            # Dispatch graph extraction before scoring
            task_run_graph_extraction.delay(content_id)
            logger.info(
                "understanding_complete",
                extra={"content_id": content_id, "domains": result.domains},
            )
            return {
                "content_id": content_id,
                "stage": "understanding",
                "domains": result.domains,
            }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 2.5: Graph extraction (Neo4j concept subgraph)
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_graph_extraction",
    max_retries=2,
    retry_backoff=True,
)
def task_run_graph_extraction(self, content_id: int) -> dict:
    """Stage 2.5: Extract concept subgraph and store in Neo4j.

    Reads:  content.pipeline_status == 'understood', summary, key_points
    Writes: concept nodes + relationships into Neo4j (non-blocking if Neo4j down)
    Next:   task_run_scoring (always, even if extraction fails)
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            title = content.title or ""
            summary = content.summary or ""
            key_points = content.key_points or []

            if not summary:
                logger.info(
                    "graph_extraction_skipped_no_summary",
                    extra={"content_id": content_id},
                )
                if content.pipeline_status == PipelineStatus.understood:
                    task_run_scoring.delay(content_id)
                return {"content_id": content_id, "stage": "graph_extraction", "skipped": True}

            # Only chain to scoring for normal pipeline flow (status == 'understood').
            # Retroactive runs on already-scored/indexed items skip scoring.
            should_run_scoring = content.pipeline_status == PipelineStatus.understood

            try:
                graph_client = _create_graph_client()
                await graph_client.connect()
                try:
                    llm_client = create_llm_client("deepseek")
                    graph_repo = GraphRepository(graph_client)
                    extractor = SubgraphExtractor(llm_client, graph_repo)
                    subgraph = await extractor.extract(
                        content_id=content_id,
                        title=title,
                        summary=summary,
                        key_points=key_points,
                    )
                    # Persist difficulty on the Neo4j Content node for later matching
                    await graph_client.execute_query(
                        "MATCH (c:Content {id: $id}) SET c.difficulty = $diff",
                        {"id": content_id, "diff": subgraph.difficulty},
                    )
                    logger.info(
                        "graph_extraction_complete",
                        extra={
                            "content_id": content_id,
                            "nodes": len(subgraph.nodes),
                            "edges": len(subgraph.edges),
                        },
                    )
                finally:
                    await graph_client.close()
            except Exception as exc:
                # Graph extraction is best-effort: log and continue pipeline
                logger.error(
                    "graph_extraction_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )

            # Always proceed to scoring if this is part of normal pipeline
            if should_run_scoring:
                task_run_scoring.delay(content_id)
            return {"content_id": content_id, "stage": "graph_extraction"}

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 3: Scoring
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_scoring",
    max_retries=3,
    retry_backoff=True,
)
def task_run_scoring(self, content_id: int) -> dict:
    """Stage 3: Run quality scoring.

    Reads:  content.pipeline_status == 'understood', summary, key_points
    Writes: quality_score + status='scored'
    Next:   task_run_indexing
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            llm_client = create_llm_client("deepseek")
            scoring_svc = ScoringService(llm_client)

            title = content.title or ""
            summary = content.summary or ""
            key_points = content.key_points or []

            try:
                score_result = await scoring_svc.score(title, summary, key_points)
            except Exception as exc:
                logger.error(
                    "scoring_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                error_json = json.dumps(
                    {
                        "failure_reason": str(exc),
                        "failed_at_stage": "scoring",
                    }
                )
                await storage.update_pipeline_status(
                    content_id, PipelineStatus.failed, error=error_json
                )
                raise self.retry(exc=exc)

            await storage.update_score(
                content_id,
                score=score_result.score,
                reasoning=score_result.reasoning,
            )
            # Dispatch next stage — NO Celery chain
            task_run_indexing.delay(content_id)
            logger.info(
                "scoring_complete",
                extra={"content_id": content_id, "score": score_result.score},
            )
            return {
                "content_id": content_id,
                "stage": "scoring",
                "score": score_result.score,
            }

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Stage 4: Indexing
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_run_indexing",
    max_retries=3,
    retry_backoff=True,
)
def task_run_indexing(self, content_id: int) -> dict:
    """Stage 4: Mark content as indexed (ready for delivery).

    Reads:  content.pipeline_status == 'scored'
    Writes: content.pipeline_status = 'indexed'
    Next:   terminal — no further dispatch
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            content = await storage.get_by_id(content_id)
            if content is None:
                raise ValueError(f"Content {content_id} not found")

            try:
                await storage.update_pipeline_status(content_id, PipelineStatus.indexed)
            except Exception as exc:
                logger.error(
                    "indexing_error",
                    extra={"content_id": content_id, "error": str(exc)},
                )
                raise self.retry(exc=exc)

            # Compute initial p_score (base: r_relevance=1.0, no user context)
            try:
                from alice.services.ranking import RankingService  # noqa: PLC0415

                ranking_svc = RankingService()
                await ranking_svc.update_p_score(session, content)
                await session.commit()
                logger.info(
                    "indexing_p_score_set",
                    extra={"content_id": content_id, "p_score": content.p_score},
                )
            except Exception:
                # p_score computation is best-effort — do not fail indexing
                logger.warning(
                    "indexing_p_score_failed",
                    extra={"content_id": content_id},
                    exc_info=True,
                )

            logger.info(
                "indexing_complete",
                extra={"content_id": content_id},
            )
            return {"content_id": content_id, "stage": "indexing"}

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Maintenance: retry failed content
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_retry_failed",
)
def task_retry_failed(self) -> dict:
    """Periodic task: re-queue content items stuck in 'failed' state.

    Triggered by Celery Beat every hour.
    Only retries items whose failure was transient (no permanent rejection flag).
    """

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            storage = ContentStorageService(session)
            failed_items = await storage.get_pending(PipelineStatus.failed, limit=50)
            requeued = 0
            for item in failed_items:
                # Skip permanently rejected content (gatekeeper rejections)
                error_data: dict = {}
                if item.pipeline_error:
                    try:
                        error_data = json.loads(item.pipeline_error)
                    except (json.JSONDecodeError, TypeError):
                        error_data = {}

                failed_stage = error_data.get("failed_at_stage", "")
                if failed_stage == "gatekeeper":
                    # Permanent rejection — do not retry
                    continue

                # Reset to fetched state so gatekeeper runs again
                await storage.update_pipeline_status(item.id, PipelineStatus.fetched)
                task_run_gatekeeper.delay(item.id)
                requeued += 1

            logger.info(
                "retry_failed_complete",
                extra={"requeued": requeued},
            )
            return {"requeued": requeued}

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Maintenance: batch update p_scores for indexed content
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_batch_update_p_scores",
)
def task_batch_update_p_scores(self) -> dict:
    """Periodic task: recompute p_score for all indexed (unpushed) content.

    Accounts for time-decay so older content's p_score naturally decreases.
    Triggered by Celery Beat daily.
    """

    async def _run() -> dict:
        from alice.services.ranking import RankingService  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            ranking_svc = RankingService()
            updated = await ranking_svc.batch_update_p_scores(session, limit=500)
            logger.info(
                "batch_p_scores_complete",
                extra={"updated": updated},
            )
            return {"updated": updated}

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Maintenance: KG update on user feedback
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_kg_feedback_update",
    max_retries=2,
    retry_backoff=True,
)
def task_kg_feedback_update(
    self, user_id: int, content_id: int, feedback_type: str
) -> dict:
    """Async task: update the user knowledge graph on feedback.

    Called from the feedback API endpoint so KG writes don't block
    the HTTP response.
    """

    async def _run() -> dict:
        graph_client = _create_graph_client()
        await graph_client.connect()
        try:
            from alice.services.kg_updater import KGUpdater  # noqa: PLC0415

            llm_client = create_llm_client("deepseek")
            updater = KGUpdater(graph_client, llm_client)
            result = await updater.update_on_feedback(
                user_id=user_id,
                content_id=content_id,
                feedback_type=feedback_type,
            )
            logger.info(
                "kg_feedback_update_complete",
                extra={
                    "user_id": user_id,
                    "content_id": content_id,
                    "feedback_type": feedback_type,
                    "concepts_updated": len(result.concepts_updated),
                    "success": result.success,
                },
            )
            return {
                "user_id": user_id,
                "content_id": content_id,
                "feedback_type": feedback_type,
                "concepts_updated": result.concepts_updated,
                "success": result.success,
            }
        except Exception as exc:
            logger.error(
                "kg_feedback_update_error",
                extra={
                    "user_id": user_id,
                    "content_id": content_id,
                    "error": str(exc),
                },
            )
            raise self.retry(exc=exc)
        finally:
            await graph_client.close()

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Push batch delivery
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_push_batch",
    max_retries=3,
    retry_backoff=True,
)
def task_push_batch(self, user_id: int, chat_id: int, limit: int = 5, content_type_filter: str | None = None) -> dict:
    """Deliver a batch of indexed content to a Telegram user.

    Reads:  content.pipeline_status == 'indexed', pushed_at IS NULL
    Writes: content.pushed_at = now(UTC) for delivered items
    Next:   terminal
    """
    from aiogram import Bot

    from alice.config import settings
    from alice.services.push import PushService

    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            svc = PushService()

            # Attempt to personalise push with KG matching (graceful degradation)
            graph_client = None
            try:
                graph_client = _create_graph_client()
                await graph_client.connect()
            except Exception:
                logger.warning(
                    "push_batch_graph_unavailable",
                    extra={"user_id": user_id},
                )
                graph_client = None

            try:
                content_list = await svc.get_next_push_batch(
                    session,
                    user_id=user_id,
                    limit=limit,
                    graph_client=graph_client,
                    content_type_filter=content_type_filter,
                )
            finally:
                if graph_client:
                    await graph_client.close()

            if not content_list:
                logger.info(
                    "push_batch_empty",
                    extra={"user_id": user_id},
                )
                return {"user_id": user_id, "delivered": 0}

            try:
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                await svc.deliver_push(
                    bot=bot,
                    user_id=user_id,
                    chat_id=chat_id,
                    content_list=content_list,
                    session=session,
                )
            except Exception as exc:
                logger.error(
                    "push_batch_error",
                    extra={"user_id": user_id, "error": str(exc)},
                )
                raise self.retry(exc=exc)

            logger.info(
                "push_batch_complete",
                extra={"user_id": user_id, "delivered": len(content_list)},
            )
            return {"user_id": user_id, "delivered": len(content_list)}

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Scheduled push: respect PushScheduler per-user
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="alice.pipeline.tasks.task_schedule_push_batches",
)
def task_schedule_push_batches(self) -> dict:
    """Periodic task: evaluate all users and dispatch push batches respecting schedule.

    For each user:
    1. Count how many items were pushed today.
    2. Check ``PushScheduler.should_push_now()`` (quiet hours + frequency cap).
    3. Determine the preferred ``content_type`` for the current time window.
    4. Dispatch ``task_push_batch`` for eligible users.

    Triggered by Celery Beat every 20 minutes.
    """

    async def _run() -> dict:
        from datetime import UTC, datetime  # noqa: PLC0415

        from sqlalchemy import func, select  # noqa: PLC0415

        from alice.models.content import Content  # noqa: PLC0415
        from alice.models.user import User  # noqa: PLC0415
        from alice.services.push_scheduler import PushScheduler  # noqa: PLC0415

        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        scheduler = PushScheduler()
        dispatched = 0
        skipped = 0

        async with AsyncSessionLocal() as session:
            users = (await session.execute(select(User))).scalars().all()

            for user in users:
                # Count items pushed today (across all content for this single-user system)
                count_result = await session.execute(
                    select(func.count(Content.id)).where(
                        Content.pushed_at >= today_start,
                    )
                )
                pushes_today = count_result.scalar_one()

                if not scheduler.should_push_now(now, pushes_today):
                    skipped += 1
                    continue

                content_type = scheduler.get_content_type_for_window(now)
                task_push_batch.delay(
                    user.id,
                    user.telegram_chat_id,
                    5,  # default batch limit
                    content_type,
                )
                dispatched += 1

        logger.info(
            "schedule_push_batches_complete",
            extra={"dispatched": dispatched, "skipped": skipped},
        )
        return {"dispatched": dispatched, "skipped": skipped}

    return asyncio.run(_run())
