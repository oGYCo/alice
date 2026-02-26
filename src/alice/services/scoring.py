# pyright: reportMissingTypeStubs=false, reportMissingImports=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
from __future__ import annotations

import json
from typing import Protocol, cast

import structlog

from alice.config.scoring import ScoringConfig
from alice.llm.protocol import LLMClient
from alice.prompts import prompt_manager
from alice.schemas.quality import (
    QualityScoreSchema,
    SevenDimensionScoreResult,
    SevenDimensionScores,
)


class _Logger(Protocol):
    def info(self, event: str, **kwargs: object) -> None: ...


class ScoringService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client: LLMClient = llm_client
        self._logger: _Logger = structlog.get_logger()

    async def score(self, title: str, summary: str, key_points: list[str]) -> QualityScoreSchema:
        prompt = prompt_manager.render_quality_score(
            title=title, summary=summary, key_points=key_points
        )
        response = await self._llm_client.complete(prompt=prompt)
        parsed = self._parse_response(response)
        if parsed is None:
            retry_prompt = (
                "Your previous response was not valid JSON. "
                "Please respond with ONLY valid JSON matching the schema."
            )
            response = await self._llm_client.complete(prompt=f"{prompt}\n\n{retry_prompt}")
            parsed = self._parse_response(response)
            if parsed is None:
                raise ValueError("LLM returned invalid JSON after retry")

        self._logger.info(
            "scoring_complete",
            score=parsed.score,
            passes_threshold=parsed.passes_threshold,
        )
        return parsed

    def _parse_response(self, response: str) -> QualityScoreSchema | None:
        try:
            data = cast(dict[str, object], json.loads(response))
        except json.JSONDecodeError:
            return None
        return QualityScoreSchema.model_validate(data)


class SevenDimensionScoringService:
    def __init__(self, llm_client: LLMClient, config: ScoringConfig | None = None) -> None:
        self._llm: LLMClient = llm_client
        self._config: ScoringConfig = config or ScoringConfig()
        self._logger: _Logger = structlog.get_logger()

    async def score(
        self,
        content_text: str,
        content_title: str = "",
        source_url: str = "",
        source_type: str = "",
    ) -> SevenDimensionScoreResult:
        prompt = prompt_manager.render(
            "quality_score_7d.j2",
            content_text=content_text,
            content_title=content_title,
            source_url=source_url,
            source_type=source_type,
        )
        response = await self._llm.complete(prompt=prompt)
        parsed = self._parse(response)
        if parsed is None:
            retry = "Your previous response was not valid JSON. Return ONLY valid JSON."
            response = await self._llm.complete(prompt=f"{prompt}\n\n{retry}")
            parsed = self._parse(response)
            if parsed is None:
                raise ValueError("LLM returned invalid JSON after retry")

        cfg = self._config
        q_total = (
            cfg.weight_substance * parsed.substance
            + cfg.weight_density * parsed.density
            + cfg.weight_credibility * parsed.credibility
            + cfg.weight_novelty * parsed.novelty
            + cfg.weight_actionability * parsed.actionability
            + cfg.weight_social_signal * parsed.social_signal
            + cfg.weight_timeliness * parsed.timeliness
        )
        result = SevenDimensionScoreResult(dimensions=parsed, q_total=round(q_total, 4))
        self._logger.info(
            "7d_scoring_complete", q_total=result.q_total, passes=result.passes_threshold
        )
        return result

    def _parse(self, response: str) -> SevenDimensionScores | None:
        try:
            data = cast(dict[str, object], json.loads(response))
        except json.JSONDecodeError:
            return None
        try:
            return SevenDimensionScores.model_validate(data)
        except Exception:
            return None
