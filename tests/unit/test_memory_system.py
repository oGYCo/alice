"""Unit tests for MemoryManager — 3-tier memory system."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alice.models.user_memory import MemoryLayer, UserMemory
from alice.services.memory_system import MemoryContext, MemoryManager


def _make_memory(
    mid: int = 1,
    user_id: int = 1,
    layer: MemoryLayer = MemoryLayer.working,
    topic: str = "test_topic",
    content: str = "test content",
    weight: float = 1.0,
    last_touched: datetime | None = None,
) -> UserMemory:
    m = MagicMock(spec=UserMemory)
    m.id = mid
    m.user_id = user_id
    m.layer = layer
    m.topic = topic
    m.content = content
    m.weight = weight
    m.last_touched = last_touched or datetime.now(UTC)
    return m


def _make_session(query_results: list | None = None) -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    result_mock.scalars.return_value.all.return_value = query_results or []
    session.execute = AsyncMock(return_value=result_mock)
    return session


manager = MemoryManager()


class TestWorkingMemory:
    async def test_declaration_creates_working_memory(self):
        session = _make_session()
        result = await manager.update_working_memory(
            session, user_id=1, declaration="Researching MoE load balancing"
        )
        session.add.assert_called_once()
        session.commit.assert_called_once()

    async def test_no_declaration_returns_none(self):
        session = _make_session()
        result = await manager.update_working_memory(session, user_id=1)
        assert result is None

    async def test_working_memory_weight_boost_set(self):
        session = _make_session()
        added_memory = None

        def capture_add(obj):
            nonlocal added_memory
            added_memory = obj

        session.add.side_effect = capture_add
        await manager.update_working_memory(session, user_id=1, declaration="MoE load balancing")
        assert added_memory is not None
        assert added_memory.weight == 3.0

    async def test_working_memory_layer_correct(self):
        session = _make_session()
        added_memory = None

        def capture_add(obj):
            nonlocal added_memory
            added_memory = obj

        session.add.side_effect = capture_add
        await manager.update_working_memory(session, user_id=1, declaration="test topic")
        assert added_memory.layer == MemoryLayer.working


class TestShortTermMemory:
    async def test_upsert_creates_new(self):
        session = _make_session()
        await manager.update_short_term(
            session, user_id=1, topic="transformers", content="attention"
        )
        session.add.assert_called_once()

    async def test_upsert_updates_existing(self):
        existing = _make_memory(layer=MemoryLayer.short_term, topic="transformers", weight=1.0)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=result_mock)

        await manager.update_short_term(session, user_id=1, topic="transformers")
        session.add.assert_not_called()
        session.commit.assert_called_once()


class TestLongTermMemory:
    async def test_promote_creates_long_term(self):
        session = _make_session()
        added = None

        def capture(obj):
            nonlocal added
            added = obj

        session.add.side_effect = capture
        await manager.promote_to_long_term(session, user_id=1, concept_id="attention_mechanism")
        assert added is not None
        assert added.layer == MemoryLayer.long_term
        assert added.topic == "attention_mechanism"


class TestGetMemoryContext:
    async def test_working_topics_in_context(self):
        w = _make_memory(layer=MemoryLayer.working, topic="MoE")
        st = _make_memory(layer=MemoryLayer.short_term, topic="CUDA")
        lt = _make_memory(layer=MemoryLayer.long_term, topic="attention")
        session = _make_session(query_results=[w, st, lt])

        ctx = await manager.get_memory_context(session, user_id=1)
        assert "MoE" in ctx.working_topics
        assert "CUDA" in ctx.short_term_topics
        assert "attention" in ctx.long_term_topics

    async def test_working_weight_boost_active_when_working_memory_exists(self):
        w = _make_memory(layer=MemoryLayer.working, topic="MoE")
        session = _make_session(query_results=[w])
        ctx = await manager.get_memory_context(session, user_id=1)
        assert ctx.working_weight_boost > 1.0

    async def test_no_working_memory_boost_is_1(self):
        session = _make_session(query_results=[])
        ctx = await manager.get_memory_context(session, user_id=1)
        assert ctx.working_weight_boost == 1.0


class TestDecayShortTerm:
    async def test_old_items_decayed(self):
        old = _make_memory(
            layer=MemoryLayer.short_term,
            topic="outdated",
            weight=1.0,
            last_touched=datetime.now(UTC) - timedelta(days=20),
        )
        session = MagicMock()
        session.commit = AsyncMock()
        session.delete = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [old]
        session.execute = AsyncMock(return_value=result_mock)

        count = await manager.decay_short_term(session, user_id=1)
        assert count == 1

    async def test_no_old_items_returns_zero(self):
        session = _make_session(query_results=[])
        count = await manager.decay_short_term(session, user_id=1)
        assert count == 0


class TestExtractTopics:
    def test_extracts_keywords(self):
        topics = MemoryManager.extract_topics_from_declaration(
            "Researching MoE load balancing algorithms"
        )
        assert len(topics) > 0

    def test_no_duplicates(self):
        topics = MemoryManager.extract_topics_from_declaration("attention attention attention")
        unique = list(set(t.lower() for t in topics))
        assert len(topics) == len(unique)
