"""Phase 2 integration tests for Alice AI Secretary.

Tests Phase 2 features against real services:
- Content-to-KG pipeline: subgraph extraction → Neo4j → GraphRAG queryable
- Feedback loop: feedback → KGUpdater → query reflects changes
- Push-to-Feed ordering: scored content → pushed → feed API → correct ranking
- Match scoring: high-match content ranks above low-match

Requires real services:
  - TEST_DATABASE_URL: PostgreSQL test database
  - NEO4J_TEST_URI: Neo4j instance (e.g. bolt://localhost:7687)

Skip automatically when environment variables are not set.
Run with:
    uv run pytest tests/integration/test_phase2_integration.py -v --timeout=120 -m integration
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.graph.client import GraphClient
from alice.graph.extractor import ContentSubgraph, ContentSubgraphNode
from alice.graph.repository import GraphRepository
from alice.graph.user_kg import UserKnowledgeGraph
from alice.llm.factory import create_llm_client
from alice.llm.protocol import LLMClient
from alice.models.base import Base
from alice.models.content import Content, PipelineStatus
from alice.models.user import User
from alice.services.kg_updater import KGUpdater
from alice.services.matching import MatchingService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# ---------------------------------------------------------------------------
# Module-level skip if required env vars are not set
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
NEO4J_TEST_URI = os.environ.get("NEO4J_TEST_URI", "")
NEO4J_TEST_USER = os.environ.get("NEO4J_TEST_USER", "neo4j")
NEO4J_TEST_PASS = os.environ.get("NEO4J_TEST_PASS", "password")
PHASE2_LLM_PROVIDER = os.environ.get("PHASE2_LLM_PROVIDER", "ollama")

_MISSING = []
if not TEST_DATABASE_URL:
    _MISSING.append("TEST_DATABASE_URL")
if not NEO4J_TEST_URI:
    _MISSING.append("NEO4J_TEST_URI")

if _MISSING:
    pytest.skip(
        f"Skipping Phase 2 integration tests — missing env vars: {', '.join(_MISSING)}",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# PostgreSQL fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create async engine connected to test DB."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="module")
async def session(engine):
    """Provide a transactional session, rolled back after each test."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess
            await sess.rollback()


# ---------------------------------------------------------------------------
# Neo4j fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def graph_client():
    """Open a GraphClient connected to the test Neo4j instance."""
    client = GraphClient(
        uri=NEO4J_TEST_URI,
        auth=(NEO4J_TEST_USER, NEO4J_TEST_PASS),
    )
    await client.connect()
    await client.ensure_schema()
    yield client
    await client.close()


@pytest.fixture
def graph_repo(graph_client: GraphClient) -> GraphRepository:
    return GraphRepository(graph_client)


@pytest.fixture
def user_kg(graph_client: GraphClient) -> UserKnowledgeGraph:
    return UserKnowledgeGraph(graph_client)


@pytest.fixture(scope="module")
def phase2_llm_client() -> LLMClient:
    """Build a real LLM client implementation for KGUpdater integration flow."""
    return create_llm_client(PHASE2_LLM_PROVIDER)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_content(
    url: str,
    title: str = "Test Content",
    summary: str = "A test summary.",
    quality_score: float = 7.5,
    p_score: float = 0.5,
    pipeline_status: PipelineStatus = PipelineStatus.indexed,
    domains: list[str] | None = None,
) -> Content:
    """Build an unsaved Content ORM object."""
    c = Content()
    c.source = "rss"
    c.source_url = url
    c.title = title
    c.summary = summary
    c.quality_score = quality_score
    c.p_score = p_score
    c.pipeline_status = pipeline_status
    c.fetched_at = datetime.now(UTC)
    c.domains = domains or ["machine_learning"]
    c.key_points = ["Key point 1", "Key point 2"]
    c.estimated_read_time = 5
    c.metadata_ = {}
    return c


def _make_user(chat_id: int = 100001) -> User:
    u = User()
    u.telegram_chat_id = chat_id
    u.preferences = {}
    return u


# ---------------------------------------------------------------------------
# Scenario 1: Content-to-KG pipeline
# ---------------------------------------------------------------------------


async def test_graph_client_health_check(graph_client: GraphClient):
    """Neo4j client connects and reports healthy."""
    ok = await graph_client.health_check()
    assert ok is True


async def test_concept_upsert_and_retrieve(graph_repo: GraphRepository, graph_client: GraphClient):
    """Upsert a concept and verify it can be retrieved via raw Cypher."""
    concept_name = "AttentionMechanism_T38"
    await graph_repo.upsert_concept(concept_name)

    rows = await graph_client.execute_query(
        "MATCH (c:Concept {name: $name}) RETURN c.name AS name",
        {"name": concept_name},
    )
    assert len(rows) == 1
    assert rows[0]["name"] == concept_name


async def test_user_knows_concept(user_kg: UserKnowledgeGraph, graph_client: GraphClient):
    """User node KNOWS a concept with a mastery level."""
    user_id = 9901
    await user_kg.ensure_user_node(user_id)
    await user_kg.add_known_concept(user_id, "TransformerT38", mastery=0.6)

    knowledge_map = await user_kg.get_knowledge_map(user_id)
    known = {k.concept: k.mastery for k in knowledge_map}
    assert "TransformerT38" in known
    assert known["TransformerT38"] == pytest.approx(0.6)


async def test_subgraph_stored_in_neo4j(graph_repo: GraphRepository, graph_client: GraphClient):
    """Manually store a ContentSubgraph in Neo4j and verify DISCUSSES edges exist."""
    content_id = 9990
    concept_name = "LoRAT38"

    # Insert content node
    await graph_client.execute_query(
        "MERGE (c:Content {id: $id}) SET c.title = $title",
        {"id": content_id, "title": "LoRA paper"},
    )
    # Insert concept node
    await graph_repo.upsert_concept(concept_name)
    # Create DISCUSSES relationship
    await graph_repo.link_content_to_concept(content_id, concept_name, "Concept")

    # Verify
    rows = await graph_client.execute_query(
        "MATCH (c:Content {id: $content_id})-[:DISCUSSES]->(concept:Concept) "
        "RETURN concept.name AS name",
        {"content_id": content_id},
    )
    concept_names = [r["name"] for r in rows]
    assert concept_name in concept_names


# ---------------------------------------------------------------------------
# Scenario 2: Feedback loop — feedback → KG update → mastery changes
# ---------------------------------------------------------------------------


async def test_positive_feedback_updates_mastery_in_neo4j(
    graph_client: GraphClient,
    graph_repo: GraphRepository,
    user_kg: UserKnowledgeGraph,
    phase2_llm_client: LLMClient,
):
    """Positive feedback raises mastery of content concepts in Neo4j."""
    user_id = 9902
    content_id = 9991
    concept_name = "AttentionT38v2"

    # Setup: user knows concept at 0.4
    await user_kg.ensure_user_node(user_id)
    await user_kg.add_known_concept(user_id, concept_name, mastery=0.4)

    # Setup: content discusses the concept
    await graph_client.execute_query("MERGE (c:Content {id: $id})", {"id": content_id})
    await graph_repo.upsert_concept(concept_name)
    await graph_client.execute_query(
        "MATCH (c:Concept {name: $name}) SET c.mastery = $mastery",
        {"name": concept_name, "mastery": 0.45},
    )
    await graph_repo.link_content_to_concept(content_id, concept_name, "Concept")

    updater = KGUpdater(graph_client=graph_client, llm_client=phase2_llm_client)
    result = await updater.update_on_feedback(user_id, content_id, "positive")

    assert result.success is True
    assert concept_name in result.concepts_updated

    # Verify new mastery in Neo4j
    new_km = await user_kg.get_knowledge_map(user_id)
    known = {k.concept: k.mastery for k in new_km}
    assert concept_name in known
    assert known[concept_name] > 0.4


async def test_negative_feedback_reduces_mastery_in_neo4j(
    graph_client: GraphClient,
    graph_repo: GraphRepository,
    user_kg: UserKnowledgeGraph,
    phase2_llm_client: LLMClient,
):
    """Negative feedback reduces mastery of content concepts in Neo4j."""
    user_id = 9903
    content_id = 9992
    concept_name = "GPT4T38"

    await user_kg.ensure_user_node(user_id)
    await user_kg.add_known_concept(user_id, concept_name, mastery=0.6)
    await graph_client.execute_query(
        "MERGE (c:Content {id: $id}) "
        "SET c.summary = $summary",
        {"id": content_id, "summary": "A deep and advanced GPT-4 systems paper."},
    )
    await graph_repo.upsert_concept(concept_name)
    await graph_client.execute_query(
        "MATCH (c:Concept {name: $name}) SET c.mastery = $mastery",
        {"name": concept_name, "mastery": 0.6},
    )
    await graph_repo.link_content_to_concept(content_id, concept_name, "Concept")

    updater = KGUpdater(graph_client=graph_client, llm_client=phase2_llm_client)
    result = await updater.update_on_feedback(user_id, content_id, "negative")

    assert result.success is True
    new_km = await user_kg.get_knowledge_map(user_id)
    known = {k.concept: k.mastery for k in new_km}
    assert known.get(concept_name, 0.6) < 0.6


async def test_save_for_later_no_mastery_change(
    graph_client: GraphClient,
    user_kg: UserKnowledgeGraph,
    phase2_llm_client: LLMClient,
):
    """Save-for-later feedback produces no changes in Neo4j mastery."""
    user_id = 9904
    concept_name = "BERTT38"

    await user_kg.ensure_user_node(user_id)
    await user_kg.add_known_concept(user_id, concept_name, mastery=0.5)

    km_before = await user_kg.get_knowledge_map(user_id)
    mastery_before = {k.concept: k.mastery for k in km_before}.get(concept_name)

    updater = KGUpdater(graph_client=graph_client, llm_client=phase2_llm_client)
    result = await updater.update_on_feedback(user_id, 9993, "save_for_later")

    assert result.success is True
    assert result.concepts_updated == []

    km_after = await user_kg.get_knowledge_map(user_id)
    mastery_after = {k.concept: k.mastery for k in km_after}.get(concept_name)
    assert mastery_before == mastery_after


# ---------------------------------------------------------------------------
# Scenario 3: Push-to-Feed ordering (PostgreSQL only)
# ---------------------------------------------------------------------------


async def test_content_ordering_by_p_score(session: AsyncSession):
    """Content items are ordered by p_score descending in the DB."""
    from sqlalchemy import select

    low = _make_content("https://example.com/low-t38", p_score=0.2)
    mid = _make_content("https://example.com/mid-t38", p_score=0.5)
    high = _make_content("https://example.com/high-t38", p_score=0.9)

    session.add_all([low, mid, high])
    await session.flush()

    result = await session.execute(
        select(Content)
        .where(
            Content.source_url.in_(
                [
                    "https://example.com/low-t38",
                    "https://example.com/mid-t38",
                    "https://example.com/high-t38",
                ]
            )
        )
        .order_by(Content.p_score.desc())
    )
    items = result.scalars().all()
    scores = [c.p_score for c in items]
    assert scores == sorted(scores, reverse=True)


async def test_push_batch_filters_unpushed(session: AsyncSession):
    """PushService.get_next_push_batch returns only unpushed indexed content."""
    from alice.services.push import PushService

    user = _make_user(chat_id=100099)
    session.add(user)
    await session.flush()

    pushed = _make_content("https://example.com/pushed-t38", p_score=0.9)
    pushed.pushed_at = datetime.now(UTC)
    pushed.pipeline_status = PipelineStatus.indexed

    unpushed = _make_content("https://example.com/unpushed-t38", p_score=0.8)
    unpushed.pipeline_status = PipelineStatus.indexed

    session.add_all([pushed, unpushed])
    await session.flush()

    svc = PushService()
    batch = await svc.get_next_push_batch(session, user.id, limit=10)
    urls = [c.source_url for c in batch]

    assert "https://example.com/unpushed-t38" in urls
    assert "https://example.com/pushed-t38" not in urls


# ---------------------------------------------------------------------------
# Scenario 4: Match scoring (unit-style with real graph)
# ---------------------------------------------------------------------------


async def test_match_score_high_for_known_concepts(
    graph_client: GraphClient, user_kg: UserKnowledgeGraph
):
    """Match score is higher when user knows the content's concepts."""
    user_id = 9905

    await user_kg.ensure_user_node(user_id)
    # User has high mastery of "AttentionT38match"
    await user_kg.add_known_concept(user_id, "AttentionT38match", mastery=0.8)

    subgraph = ContentSubgraph(
        nodes=[
            ContentSubgraphNode(
                name="AttentionT38match",
                type="concept",
            )
        ],
        edges=[],
        difficulty=0.7,
        entry_concepts=["AttentionT38match"],
    )

    svc = MatchingService(client=graph_client)
    high_result = await svc.compute_match_score(
        user_id=user_id,
        subgraph=subgraph,
    )
    assert high_result.match_score > 0.3


async def test_match_score_lower_for_unknown_concepts(
    graph_client: GraphClient, user_kg: UserKnowledgeGraph
):
    """Match score is lower when user doesn't know the content's concepts."""
    user_id = 9906

    await user_kg.ensure_user_node(user_id)
    # User knows nothing about "QuantumComputingT38"

    subgraph = ContentSubgraph(
        nodes=[
            ContentSubgraphNode(
                name="QuantumComputingT38",
                type="concept",
            )
        ],
        edges=[],
        difficulty=0.9,
        entry_concepts=["QuantumComputingT38"],
    )

    svc = MatchingService(client=graph_client)
    low_result = await svc.compute_match_score(
        user_id=user_id,
        subgraph=subgraph,
    )
    assert low_result.match_score < 0.5


async def test_high_match_ranks_above_low_match(
    graph_client: GraphClient, user_kg: UserKnowledgeGraph
):
    """High-match content should produce a higher match_score than low-match content."""
    user_id = 9907

    await user_kg.ensure_user_node(user_id)
    await user_kg.add_known_concept(user_id, "NLPConceptT38", mastery=0.85)

    high_subgraph = ContentSubgraph(
        nodes=[
            ContentSubgraphNode(
                name="NLPConceptT38",
                type="concept",
            )
        ],
        edges=[],
        difficulty=0.7,
        entry_concepts=["NLPConceptT38"],
    )
    low_subgraph = ContentSubgraph(
        nodes=[
            ContentSubgraphNode(
                name="UnknownTopicT38XYZ",
                type="concept",
            )
        ],
        edges=[],
        difficulty=0.9,
        entry_concepts=["UnknownTopicT38XYZ"],
    )

    svc = MatchingService(client=graph_client)
    high_result = await svc.compute_match_score(
        user_id=user_id,
        subgraph=high_subgraph,
    )
    low_result = await svc.compute_match_score(
        user_id=user_id,
        subgraph=low_subgraph,
    )

    assert high_result.match_score > low_result.match_score
