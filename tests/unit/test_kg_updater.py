"""Unit tests for KGUpdater — knowledge graph updates on user feedback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alice.graph.client import GraphClient
from alice.graph.user_kg import UserKnowledgeGraph
from alice.llm.protocol import LLMClient
from alice.services.kg_updater import _EXPLAIN_MASTERY, _SEEN_MASTERY, KGUpdater

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_updater(
    concept_rows: list[dict] | None = None,
    prereq_rows: list[dict] | None = None,
    summary_rows: list[dict] | None = None,
    llm_response: str = "mismatch: topic too advanced",
) -> tuple[KGUpdater, MagicMock, MagicMock, MagicMock]:
    """Create a KGUpdater with mocked GraphClient, UserKnowledgeGraph, and LLMClient."""
    mock_client = MagicMock(spec=GraphClient)
    mock_ukg = MagicMock(spec=UserKnowledgeGraph)
    mock_llm = MagicMock(spec=LLMClient)

    # Default responses
    _concept_rows = (
        concept_rows
        if concept_rows is not None
        else [
            {"name": "Attention", "mastery": 0.5},
            {"name": "Transformer", "mastery": 0.4},
        ]
    )
    _prereq_rows = prereq_rows if prereq_rows is not None else []
    _summary_rows = summary_rows if summary_rows is not None else []

    # execute_query: first call returns concepts, second call (for prereqs or summary) varies
    call_count = {"n": 0}

    async def side_execute(cypher: str, params: dict | None = None):  # noqa: ANN001
        call_count["n"] += 1
        if "summary" in cypher:
            return _summary_rows
        if "PREREQUISITE_OF" in cypher:
            return _prereq_rows
        if "DISCUSSES" in cypher:
            return _concept_rows
        return []

    mock_client.execute_query = AsyncMock(side_effect=side_execute)
    mock_ukg.update_mastery = AsyncMock()
    mock_llm.complete = AsyncMock(return_value=llm_response)

    with patch("alice.services.kg_updater.UserKnowledgeGraph", return_value=mock_ukg):
        updater = KGUpdater(graph_client=mock_client, llm_client=mock_llm)

    return updater, mock_client, mock_ukg, mock_llm


# ── Tests: positive feedback ──────────────────────────────────────────────────


async def test_positive_feedback_boosts_mastery():
    """Positive feedback: concepts in content get mastery +0.15."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.5}],
    )
    result = await updater.update_on_feedback(1, 10, "positive")

    assert result.success is True
    assert "Attention" in result.concepts_updated
    assert result.mastery_changes["Attention"] == pytest.approx(0.65)
    mock_ukg.update_mastery.assert_any_call(1, "Attention", pytest.approx(0.65))


async def test_positive_feedback_inferential_boost():
    """Positive feedback: prerequisite concepts get +0.075 (POSITIVE_BOOST * 0.5)."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[{"name": "Transformer", "mastery": 0.5}],
        prereq_rows=[{"prereq_name": "Attention", "mastery": 0.3}],
    )
    result = await updater.update_on_feedback(1, 10, "positive")

    assert "Attention" in result.concepts_updated
    assert result.mastery_changes["Attention"] == pytest.approx(0.375)  # 0.3 + 0.075
    mock_ukg.update_mastery.assert_any_call(1, "Attention", pytest.approx(0.375))


async def test_positive_feedback_mastery_clamped_at_1():
    """Mastery cannot exceed 1.0 even with repeated positive feedback."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.95}],
    )
    result = await updater.update_on_feedback(1, 10, "positive")

    assert result.mastery_changes["Attention"] == pytest.approx(1.0)
    mock_ukg.update_mastery.assert_any_call(1, "Attention", pytest.approx(1.0))


# ── Tests: seen feedback ──────────────────────────────────────────────────────


async def test_seen_feedback_sets_mastery_to_1():
    """Seen feedback: all content concepts get mastery = 1.0."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[
            {"name": "Attention", "mastery": 0.5},
            {"name": "Transformer", "mastery": 0.7},
        ],
    )
    result = await updater.update_on_feedback(1, 10, "seen")

    assert result.success is True
    assert result.mastery_changes["Attention"] == _SEEN_MASTERY
    assert result.mastery_changes["Transformer"] == _SEEN_MASTERY
    assert mock_ukg.update_mastery.call_count == 2


# ── Tests: negative feedback ──────────────────────────────────────────────────


async def test_negative_feedback_reduces_mastery():
    """Negative feedback: mastery decreases by 0.1."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.5}],
        summary_rows=[{"summary": "Paper about attention mechanism"}],
    )
    result = await updater.update_on_feedback(1, 10, "negative")

    assert result.success is True
    assert result.mastery_changes["Attention"] == pytest.approx(0.4)
    mock_ukg.update_mastery.assert_any_call(1, "Attention", pytest.approx(0.4))


async def test_negative_feedback_mastery_clamped_at_0():
    """Mastery cannot go below 0.0 with negative feedback."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.05}],
        summary_rows=[],
    )
    result = await updater.update_on_feedback(1, 10, "negative")

    assert result.mastery_changes["Attention"] == pytest.approx(0.0)


async def test_negative_feedback_triggers_llm_analysis():
    """Negative feedback with content summary: LLM called for mismatch analysis."""
    updater, _, _, mock_llm = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.5}],
        summary_rows=[{"summary": "Deep paper about transformers"}],
    )
    await updater.update_on_feedback(1, 10, "negative")

    mock_llm.complete.assert_called_once()
    call_args = mock_llm.complete.call_args[0][0]
    assert "Deep paper about transformers" in call_args
    assert "mismatch" in call_args.lower()


async def test_negative_feedback_no_llm_if_no_summary():
    """Negative feedback without content in Neo4j: LLM not called."""
    updater, _, _, mock_llm = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.5}],
        summary_rows=[],  # No content summary in Neo4j
    )
    await updater.update_on_feedback(1, 10, "negative")

    mock_llm.complete.assert_not_called()


# ── Tests: explain_concept feedback ──────────────────────────────────────────


async def test_explain_concept_sets_mastery_to_01():
    """Explain concept feedback: mastery set to 0.1 (recording a gap)."""
    updater, _, mock_ukg, _ = _make_updater(
        concept_rows=[{"name": "Attention", "mastery": 0.5}],
    )
    result = await updater.update_on_feedback(1, 10, "explain_concept")

    assert result.success is True
    assert result.mastery_changes["Attention"] == _EXPLAIN_MASTERY
    mock_ukg.update_mastery.assert_called_once_with(1, "Attention", _EXPLAIN_MASTERY)


# ── Tests: save_for_later feedback ────────────────────────────────────────────


async def test_save_for_later_no_kg_change():
    """Save for later: no mastery changes, no graph writes."""
    updater, mock_client, mock_ukg, _ = _make_updater()
    result = await updater.update_on_feedback(1, 10, "save_for_later")

    assert result.success is True
    assert result.concepts_updated == []
    assert result.mastery_changes == {}
    mock_ukg.update_mastery.assert_not_called()


# ── Tests: edge cases ─────────────────────────────────────────────────────────


async def test_content_not_in_graph_returns_empty():
    """If content has no concepts in Neo4j, return empty result (success=True)."""
    updater, _, mock_ukg, _ = _make_updater(concept_rows=[])
    result = await updater.update_on_feedback(1, 10, "positive")

    assert result.success is True
    assert result.concepts_updated == []
    assert result.mastery_changes == {}
    mock_ukg.update_mastery.assert_not_called()


async def test_exception_returns_failure_result():
    """If Neo4j query fails, return KGUpdateResult(success=False, error=...)."""
    mock_client = MagicMock(spec=GraphClient)
    mock_client.execute_query = AsyncMock(side_effect=RuntimeError("connection refused"))
    mock_llm = MagicMock(spec=LLMClient)

    with patch("alice.services.kg_updater.UserKnowledgeGraph", return_value=MagicMock()):
        updater = KGUpdater(graph_client=mock_client, llm_client=mock_llm)

    result = await updater.update_on_feedback(1, 10, "positive")

    assert result.success is False
    assert "connection refused" in result.error
    assert result.concepts_updated == []


async def test_update_result_has_mastery_changes_dict():
    """mastery_changes dict is populated with concept -> new_mastery entries."""
    updater, _, _, _ = _make_updater(
        concept_rows=[
            {"name": "Attention", "mastery": 0.5},
            {"name": "Transformer", "mastery": 0.3},
        ],
    )
    result = await updater.update_on_feedback(1, 10, "positive")

    assert isinstance(result.mastery_changes, dict)
    assert "Attention" in result.mastery_changes
    assert "Transformer" in result.mastery_changes
    assert result.mastery_changes["Attention"] == pytest.approx(0.65)
    assert result.mastery_changes["Transformer"] == pytest.approx(0.45)


async def test_unknown_feedback_type_returns_success():
    """Unknown feedback type: no crash, return empty result with success=True."""
    updater, _, mock_ukg, _ = _make_updater()
    result = await updater.update_on_feedback(1, 10, "unknown_type")

    assert result.success is True
    assert result.concepts_updated == []
    mock_ukg.update_mastery.assert_not_called()
