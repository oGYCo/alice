"""Advanced feedback skill system with YAML registry and periodic self-review."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

import structlog
import yaml

from alice.services.kg_updater import KGUpdateResult, KGUpdater


class _Logger(Protocol):
    def info(self, event: str, **kw: object) -> None: ...
    def warning(self, event: str, **kw: object) -> None: ...
    def debug(self, event: str, **kw: object) -> None: ...


logger = cast(_Logger, structlog.get_logger(__name__))

_DEFAULT_SKILLS_PATH = Path(__file__).parent.parent.parent.parent / "config" / "skills.yaml"


class FeedbackType(StrEnum):
    """All feedback types that can trigger skills."""

    positive_feedback = "positive_feedback"
    learned_new = "learned_new"
    negative_feedback = "negative_feedback"
    already_known = "already_known"
    too_hard = "too_hard"
    too_easy = "too_easy"
    explain_concept = "explain_concept"
    explore_new_topic = "explore_new_topic"
    positive_on_unexpected = "positive_on_unexpected"
    weekly_cron = "weekly_cron"


@dataclass
class Skill:
    """A single skill definition loaded from YAML."""

    name: str
    triggers: list[str]
    actions: list[str]


@dataclass
class SkillContext:
    """Context passed to skill execution."""

    user_id: int
    content_id: int | None = None
    feedback_type: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result of executing a skill."""

    skill_name: str
    success: bool
    actions_run: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SelfReviewReport:
    """Output of periodic_self_review skill."""

    user_id: int
    feedback_stats: dict[str, int]
    preference_drift: list[str]
    knowledge_gaps: list[str]
    diff_summary: str


class SkillExecutor:
    """Executes skills based on feedback type using YAML skill registry.

    Delegates KG-related skills to KGUpdater. Implements periodic_self_review
    as an in-process analysis (no external deps).
    """

    def __init__(
        self,
        kg_updater: KGUpdater | None = None,
        skills_path: Path | None = None,
    ) -> None:
        self._kg_updater = kg_updater
        self._skills: dict[str, Skill] = {}
        path = skills_path or _DEFAULT_SKILLS_PATH
        self._load_skills(path)

    def _load_skills(self, path: Path) -> None:
        if not path.exists():
            logger.warning("skills_yaml_not_found", path=str(path))
            return
        with path.open() as f:
            raw = yaml.safe_load(f)
        for name, defn in (raw.get("skills") or {}).items():
            self._skills[name] = Skill(
                name=name,
                triggers=defn.get("trigger", []),
                actions=defn.get("actions", []),
            )
        logger.info("skills_loaded", count=len(self._skills))

    def get_triggered_skills(self, feedback_type: FeedbackType | str) -> list[Skill]:
        """Return all skills whose trigger list includes the given feedback type."""
        ft = str(feedback_type)
        return [s for s in self._skills.values() if ft in s.triggers]

    async def execute(self, skill_name: str, context: SkillContext) -> SkillResult:
        """Execute a named skill in the given context."""
        skill = self._skills.get(skill_name)
        if skill is None:
            logger.warning("unknown_skill", skill_name=skill_name)
            return SkillResult(skill_name=skill_name, success=False, error="skill_not_found")

        logger.info(
            "skill_executing",
            skill=skill_name,
            user_id=context.user_id,
            content_id=context.content_id,
        )

        if skill_name == "periodic_self_review":
            return await self._run_periodic_self_review(skill, context)

        if skill_name in (
            "update_knowledge_graph",
            "adjust_preferences",
            "calibrate_difficulty",
            "discover_interest",
        ):
            return await self._delegate_to_kg_updater(skill, context)

        return SkillResult(
            skill_name=skill_name,
            success=True,
            actions_run=skill.actions,
            data={"note": "stub_execution"},
        )

    async def execute_for_feedback(
        self, feedback_type: FeedbackType | str, context: SkillContext
    ) -> list[SkillResult]:
        """Execute all skills triggered by the given feedback type."""
        triggered = self.get_triggered_skills(feedback_type)
        results = []
        for skill in triggered:
            result = await self.execute(skill.name, context)
            results.append(result)
        return results

    async def _delegate_to_kg_updater(self, skill: Skill, context: SkillContext) -> SkillResult:
        if self._kg_updater is None:
            return SkillResult(
                skill_name=skill.name,
                success=True,
                actions_run=skill.actions,
                data={"note": "no_kg_updater_configured"},
            )

        feedback_map = {
            "update_knowledge_graph": "positive",
            "adjust_preferences": "negative",
            "calibrate_difficulty": "seen",
            "discover_interest": "explain_concept",
        }
        fb_type = feedback_map.get(skill.name, "positive")
        content_id = context.content_id or 0

        try:
            kg_result: KGUpdateResult = await self._kg_updater.update_on_feedback(
                user_id=context.user_id,
                content_id=content_id,
                feedback_type=fb_type,
            )
            return SkillResult(
                skill_name=skill.name,
                success=kg_result.success,
                actions_run=skill.actions,
                data={
                    "concepts_updated": kg_result.concepts_updated,
                    "mastery_changes": kg_result.mastery_changes,
                },
                error=kg_result.error,
            )
        except Exception as exc:
            return SkillResult(
                skill_name=skill.name,
                success=False,
                error=str(exc),
            )

    async def _run_periodic_self_review(self, skill: Skill, context: SkillContext) -> SkillResult:
        """Analyse feedback history to detect drift and knowledge gaps."""
        extra = context.extra or {}
        feedback_history: list[dict] = extra.get("feedback_history", [])

        stats: dict[str, int] = {}
        for item in feedback_history:
            ft = str(item.get("feedback_type", "unknown"))
            stats[ft] = stats.get(ft, 0) + 1

        positive_count = stats.get("positive_feedback", 0) + stats.get("learned_new", 0)
        negative_count = stats.get("negative_feedback", 0) + stats.get("already_known", 0)
        total = len(feedback_history)

        drift: list[str] = []
        if total > 0:
            negative_ratio = negative_count / total
            if negative_ratio > 0.4:
                drift.append("high_negative_ratio: content relevance may be degrading")
            if stats.get("too_hard", 0) > total * 0.3:
                drift.append("content_too_hard: difficulty settings need recalibration")
            if stats.get("too_easy", 0) > total * 0.3:
                drift.append("content_too_easy: user knowledge may have advanced")

        gaps: list[str] = []
        for item in feedback_history:
            if item.get("feedback_type") == "explain_concept":
                concept = item.get("concept", "")
                if concept and concept not in gaps:
                    gaps.append(concept)

        diff_parts = []
        if drift:
            diff_parts.append(f"Drift detected: {'; '.join(drift)}")
        if gaps:
            diff_parts.append(f"Knowledge gaps: {', '.join(gaps)}")
        if positive_count > 0:
            diff_parts.append(f"Positive engagement: {positive_count}/{total} items")

        report = SelfReviewReport(
            user_id=context.user_id,
            feedback_stats=stats,
            preference_drift=drift,
            knowledge_gaps=gaps,
            diff_summary=" | ".join(diff_parts) if diff_parts else "No significant drift detected",
        )

        logger.info(
            "self_review_complete",
            user_id=context.user_id,
            drift_count=len(drift),
            gap_count=len(gaps),
        )

        return SkillResult(
            skill_name=skill.name,
            success=True,
            actions_run=skill.actions,
            data={
                "feedback_stats": report.feedback_stats,
                "preference_drift": report.preference_drift,
                "knowledge_gaps": report.knowledge_gaps,
                "diff_summary": report.diff_summary,
            },
        )

    @property
    def skill_names(self) -> list[str]:
        return list(self._skills.keys())
