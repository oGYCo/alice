"""Tests for the SkillExecutor — advanced feedback skill dispatch system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from alice.services.kg_updater import KGUpdateResult
from alice.services.skill_executor import (
    FeedbackType,
    Skill,
    SkillContext,
    SkillExecutor,
    SkillResult,
    _DEFAULT_SKILLS_PATH,
)

# Path to the real skills.yaml used in all tests
_SKILLS_YAML = Path(__file__).parent.parent.parent / "config" / "skills.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def executor() -> SkillExecutor:
    """SkillExecutor with real skills.yaml and no KGUpdater."""
    return SkillExecutor(skills_path=_SKILLS_YAML)


@pytest.fixture()
def context() -> SkillContext:
    return SkillContext(user_id=42, content_id=99, feedback_type="positive_feedback")


@pytest.fixture()
def mock_kg_updater() -> MagicMock:
    kg = MagicMock()
    kg.update_on_feedback = AsyncMock(
        return_value=KGUpdateResult(
            user_id=42,
            content_id=99,
            feedback_type="positive",
            concepts_updated=["transformer", "attention"],
            mastery_changes={"transformer": 0.85},
            success=True,
        )
    )
    return kg


@pytest.fixture()
def executor_with_kg(mock_kg_updater: MagicMock) -> SkillExecutor:
    return SkillExecutor(kg_updater=mock_kg_updater, skills_path=_SKILLS_YAML)


# ---------------------------------------------------------------------------
# 1. Loading skills from YAML
# ---------------------------------------------------------------------------


def test_load_skills_from_yaml_returns_five_skills(executor: SkillExecutor) -> None:
    """skills.yaml defines exactly 5 skills."""
    assert len(executor.skill_names) == 5


def test_skill_names_contains_expected_keys(executor: SkillExecutor) -> None:
    expected = {
        "update_knowledge_graph",
        "adjust_preferences",
        "calibrate_difficulty",
        "discover_interest",
        "periodic_self_review",
    }
    assert set(executor.skill_names) == expected


def test_default_skills_path_points_to_config_yaml() -> None:
    """The default path constant resolves to config/skills.yaml at project root."""
    assert _DEFAULT_SKILLS_PATH.name == "skills.yaml"
    assert _DEFAULT_SKILLS_PATH.parent.name == "config"
    assert _DEFAULT_SKILLS_PATH.exists()


def test_missing_yaml_does_not_raise(tmp_path: Path) -> None:
    """SkillExecutor with a non-existent path loads zero skills gracefully."""
    ex = SkillExecutor(skills_path=tmp_path / "nonexistent.yaml")
    assert ex.skill_names == []


# ---------------------------------------------------------------------------
# 2. Trigger mapping
# ---------------------------------------------------------------------------


def test_positive_feedback_triggers_update_knowledge_graph(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.positive_feedback)
    names = [s.name for s in triggered]
    assert "update_knowledge_graph" in names


def test_learned_new_also_triggers_update_knowledge_graph(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.learned_new)
    names = [s.name for s in triggered]
    assert "update_knowledge_graph" in names


def test_negative_feedback_triggers_adjust_preferences(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.negative_feedback)
    names = [s.name for s in triggered]
    assert "adjust_preferences" in names


def test_already_known_triggers_adjust_preferences(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.already_known)
    names = [s.name for s in triggered]
    assert "adjust_preferences" in names


def test_too_hard_triggers_calibrate_difficulty(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.too_hard)
    names = [s.name for s in triggered]
    assert "calibrate_difficulty" in names


def test_weekly_cron_triggers_periodic_self_review(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.weekly_cron)
    names = [s.name for s in triggered]
    assert "periodic_self_review" in names


def test_explore_new_topic_triggers_discover_interest(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills(FeedbackType.explore_new_topic)
    names = [s.name for s in triggered]
    assert "discover_interest" in names


def test_unknown_feedback_type_returns_empty_list(executor: SkillExecutor) -> None:
    triggered = executor.get_triggered_skills("nonexistent_feedback_type")
    assert triggered == []


# ---------------------------------------------------------------------------
# 3. execute() — named skill dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_unknown_skill_returns_failure(
    executor: SkillExecutor, context: SkillContext
) -> None:
    result = await executor.execute("nonexistent_skill", context)
    assert result.success is False
    assert result.error == "skill_not_found"
    assert result.skill_name == "nonexistent_skill"


@pytest.mark.asyncio
async def test_execute_update_knowledge_graph_without_kg_updater(
    executor: SkillExecutor, context: SkillContext
) -> None:
    """Without a KGUpdater, the KG skills still succeed with a 'no_kg_updater_configured' note."""
    result = await executor.execute("update_knowledge_graph", context)
    assert result.success is True
    assert result.data.get("note") == "no_kg_updater_configured"


@pytest.mark.asyncio
async def test_execute_update_knowledge_graph_with_kg_updater(
    executor_with_kg: SkillExecutor,
    mock_kg_updater: MagicMock,
    context: SkillContext,
) -> None:
    result = await executor_with_kg.execute("update_knowledge_graph", context)
    assert result.success is True
    assert result.skill_name == "update_knowledge_graph"
    assert "transformer" in result.data.get("concepts_updated", [])
    mock_kg_updater.update_on_feedback.assert_called_once_with(
        user_id=42,
        content_id=99,
        feedback_type="positive",
    )


@pytest.mark.asyncio
async def test_execute_adjust_preferences_delegates_negative_feedback(
    executor_with_kg: SkillExecutor,
    mock_kg_updater: MagicMock,
    context: SkillContext,
) -> None:
    result = await executor_with_kg.execute("adjust_preferences", context)
    assert result.success is True
    mock_kg_updater.update_on_feedback.assert_called_once_with(
        user_id=42,
        content_id=99,
        feedback_type="negative",
    )


@pytest.mark.asyncio
async def test_execute_calibrate_difficulty_delegates_seen(
    executor_with_kg: SkillExecutor,
    mock_kg_updater: MagicMock,
    context: SkillContext,
) -> None:
    result = await executor_with_kg.execute("calibrate_difficulty", context)
    assert result.success is True
    mock_kg_updater.update_on_feedback.assert_called_once_with(
        user_id=42,
        content_id=99,
        feedback_type="seen",
    )


@pytest.mark.asyncio
async def test_execute_discover_interest_delegates_explain_concept(
    executor_with_kg: SkillExecutor,
    mock_kg_updater: MagicMock,
    context: SkillContext,
) -> None:
    result = await executor_with_kg.execute("discover_interest", context)
    assert result.success is True
    mock_kg_updater.update_on_feedback.assert_called_once_with(
        user_id=42,
        content_id=99,
        feedback_type="explain_concept",
    )


@pytest.mark.asyncio
async def test_execute_kg_updater_exception_returns_failure(
    context: SkillContext,
) -> None:
    kg = MagicMock()
    kg.update_on_feedback = AsyncMock(side_effect=RuntimeError("neo4j down"))
    ex = SkillExecutor(kg_updater=kg, skills_path=_SKILLS_YAML)
    result = await ex.execute("update_knowledge_graph", context)
    assert result.success is False
    assert "neo4j down" in (result.error or "")


# ---------------------------------------------------------------------------
# 4. execute_for_feedback() — fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_for_feedback_positive_returns_one_result(
    executor: SkillExecutor, context: SkillContext
) -> None:
    results = await executor.execute_for_feedback(FeedbackType.positive_feedback, context)
    assert len(results) == 1
    assert results[0].skill_name == "update_knowledge_graph"


@pytest.mark.asyncio
async def test_execute_for_feedback_negative_returns_one_result(
    executor: SkillExecutor, context: SkillContext
) -> None:
    results = await executor.execute_for_feedback(FeedbackType.negative_feedback, context)
    assert len(results) == 1
    assert results[0].skill_name == "adjust_preferences"


@pytest.mark.asyncio
async def test_execute_for_feedback_weekly_cron_returns_self_review(
    executor: SkillExecutor,
) -> None:
    ctx = SkillContext(
        user_id=1,
        extra={
            "feedback_history": [
                {"feedback_type": "positive_feedback"},
                {"feedback_type": "positive_feedback"},
                {"feedback_type": "negative_feedback"},
            ]
        },
    )
    results = await executor.execute_for_feedback(FeedbackType.weekly_cron, ctx)
    assert len(results) == 1
    assert results[0].skill_name == "periodic_self_review"
    assert results[0].success is True


# ---------------------------------------------------------------------------
# 5. periodic_self_review — analysis logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_review_no_history_returns_no_drift(executor: SkillExecutor) -> None:
    ctx = SkillContext(user_id=1, extra={"feedback_history": []})
    result = await executor.execute("periodic_self_review", ctx)
    assert result.success is True
    assert result.data["preference_drift"] == []
    assert result.data["knowledge_gaps"] == []
    assert "No significant drift detected" in result.data["diff_summary"]


@pytest.mark.asyncio
async def test_self_review_high_negative_ratio_detected(executor: SkillExecutor) -> None:
    history = [{"feedback_type": "negative_feedback"}] * 5 + [
        {"feedback_type": "positive_feedback"}
    ] * 1
    ctx = SkillContext(user_id=1, extra={"feedback_history": history})
    result = await executor.execute("periodic_self_review", ctx)
    assert any("high_negative_ratio" in d for d in result.data["preference_drift"])


@pytest.mark.asyncio
async def test_self_review_too_hard_drift_detected(executor: SkillExecutor) -> None:
    history = [{"feedback_type": "too_hard"}] * 4 + [{"feedback_type": "positive_feedback"}] * 2
    ctx = SkillContext(user_id=1, extra={"feedback_history": history})
    result = await executor.execute("periodic_self_review", ctx)
    assert any("content_too_hard" in d for d in result.data["preference_drift"])


@pytest.mark.asyncio
async def test_self_review_knowledge_gaps_from_explain_concept(executor: SkillExecutor) -> None:
    history = [
        {"feedback_type": "explain_concept", "concept": "attention_mechanism"},
        {"feedback_type": "explain_concept", "concept": "positional_encoding"},
        {"feedback_type": "explain_concept", "concept": "attention_mechanism"},  # duplicate
    ]
    ctx = SkillContext(user_id=1, extra={"feedback_history": history})
    result = await executor.execute("periodic_self_review", ctx)
    gaps = result.data["knowledge_gaps"]
    assert "attention_mechanism" in gaps
    assert "positional_encoding" in gaps
    assert gaps.count("attention_mechanism") == 1  # deduped


@pytest.mark.asyncio
async def test_self_review_feedback_stats_counted_correctly(executor: SkillExecutor) -> None:
    history = [
        {"feedback_type": "positive_feedback"},
        {"feedback_type": "positive_feedback"},
        {"feedback_type": "negative_feedback"},
    ]
    ctx = SkillContext(user_id=1, extra={"feedback_history": history})
    result = await executor.execute("periodic_self_review", ctx)
    stats = result.data["feedback_stats"]
    assert stats["positive_feedback"] == 2
    assert stats["negative_feedback"] == 1


@pytest.mark.asyncio
async def test_self_review_diff_summary_includes_positive_engagement(
    executor: SkillExecutor,
) -> None:
    history = [
        {"feedback_type": "positive_feedback"},
        {"feedback_type": "learned_new"},
        {"feedback_type": "positive_feedback"},
    ]
    ctx = SkillContext(user_id=1, extra={"feedback_history": history})
    result = await executor.execute("periodic_self_review", ctx)
    assert "Positive engagement" in result.data["diff_summary"]
