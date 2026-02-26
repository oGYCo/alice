import json

import pytest

from alice.llm.mock import MockLLMClient
from alice.schemas.content import ContentUnderstandingSchema
from alice.services.understanding import UnderstandingService


@pytest.fixture()
def sample_payload() -> dict:
    return {
        "summary": "Concise summary.",
        "key_points": ["Point 1", "Point 2"],
        "domains": ["machine learning", "nlp"],
        "estimated_read_time": 5,
    }


async def test_understanding_parses_fixture_response() -> None:
    client = MockLLMClient(fixture_name="understanding_response")
    service = UnderstandingService(client)

    result = await service.process(title="Test", text="Body", language="en")

    assert isinstance(result, ContentUnderstandingSchema)
    assert result.summary
    assert result.key_points
    assert result.domains
    assert result.estimated_read_time >= 1


async def test_understanding_retries_on_invalid_json(sample_payload: dict) -> None:
    client = MockLLMClient()
    client.set_responses(["not-json", json.dumps(sample_payload)])
    service = UnderstandingService(client)

    result = await service.process(title="Test", text="Body", language="en")

    assert result == ContentUnderstandingSchema.model_validate(sample_payload)


async def test_understanding_raises_after_second_invalid_json() -> None:
    client = MockLLMClient()
    client.set_responses(["nope", "still not json"])
    service = UnderstandingService(client)

    with pytest.raises(ValueError, match="LLM returned invalid JSON after retry"):
        await service.process(title="Test", text="Body", language="en")


async def test_understanding_chinese_content(sample_payload: dict) -> None:
    client = MockLLMClient()
    client.set_responses([json.dumps(sample_payload)])
    service = UnderstandingService(client)

    result = await service.process(title="标题", text="正文", language="zh")

    assert result == ContentUnderstandingSchema.model_validate(sample_payload)
