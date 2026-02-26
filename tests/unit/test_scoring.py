# pyright: reportMissingImports=false, reportMissingTypeStubs=false

import json

import pytest

from alice.llm.mock import MockLLMClient
from alice.schemas.quality import QualityScoreSchema
from alice.services.scoring import ScoringService


async def test_scoring_parses_fixture_response() -> None:
    client = MockLLMClient(fixture_name="quality_score")
    service = ScoringService(client)

    result = await service.score(
        title="Test Title",
        summary="Concise summary",
        key_points=["Point 1", "Point 2"],
    )

    assert isinstance(result, QualityScoreSchema)
    assert result.score == 8.5
    assert result.passes_threshold is True


@pytest.mark.parametrize(
    ("score", "passes"),
    [(4.0, False), (6.0, True), (5.9, False)],
)
async def test_scoring_threshold_boundaries(score: float, passes: bool) -> None:
    client = MockLLMClient()
    client.set_responses([json.dumps({"score": score, "reasoning": "Reason"})])
    service = ScoringService(client)

    result = await service.score(
        title="Test",
        summary="Summary",
        key_points=["Point"],
    )

    assert result.score == score
    assert result.passes_threshold is passes


async def test_scoring_retries_on_invalid_json() -> None:
    client = MockLLMClient()
    client.set_responses(
        [
            "not-json",
            json.dumps({"score": 7.0, "reasoning": "Valid"}),
        ]
    )
    service = ScoringService(client)

    result = await service.score(
        title="Test",
        summary="Summary",
        key_points=["Point"],
    )

    assert result.score == 7.0
    assert result.passes_threshold is True


async def test_scoring_raises_after_second_invalid_json() -> None:
    client = MockLLMClient()
    client.set_responses(["nope", "still not json"])
    service = ScoringService(client)

    with pytest.raises(ValueError, match="LLM returned invalid JSON after retry"):
        _ = await service.score(
            title="Test",
            summary="Summary",
            key_points=["Point"],
        )
