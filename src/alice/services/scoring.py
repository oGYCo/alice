# pyright: reportMissingTypeStubs=false, reportMissingImports=false
from __future__ import annotations

import json
from typing import Protocol, cast

import structlog

from alice.llm.protocol import LLMClient
from alice.prompts import prompt_manager
from alice.schemas.quality import QualityScoreSchema


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
