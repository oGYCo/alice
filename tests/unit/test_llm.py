"""Tests for LLM abstraction layer."""

import json

import pytest

from alice.llm.factory import create_llm_client
from alice.llm.mock import MockLLMClient
from alice.llm.protocol import LLMClient
from alice.schemas.gatekeeper import GatekeeperDecision
from alice.schemas.quality import QualityScoreSchema


@pytest.fixture
def mock_client():
    return MockLLMClient()


async def test_mock_client_complete_returns_string(mock_client):
    """Test that mock client complete() returns a string."""
    mock_client.set_responses(['{"status": "ok"}'])
    result = await mock_client.complete("test prompt")
    assert isinstance(result, str)


async def test_mock_client_multiple_responses(mock_client):
    """Test that mock client cycles through responses."""
    mock_client.set_responses(["response 1", "response 2"])
    r1 = await mock_client.complete("prompt 1")
    r2 = await mock_client.complete("prompt 2")
    assert r1 == "response 1"
    assert r2 == "response 2"


async def test_mock_client_structured_gatekeeper(mock_client):
    """Test mock client returns parsed GatekeeperDecision."""
    mock_client.set_responses(
        ['{"passed": true, "reason": "good", "confidence": 0.9, "method": "ollama"}']
    )
    result = await mock_client.complete_structured("test", GatekeeperDecision)
    assert isinstance(result, GatekeeperDecision)
    assert result.passed is True
    assert result.confidence == 0.9


async def test_mock_client_structured_quality(mock_client):
    """Test mock client returns parsed QualityScoreSchema."""
    mock_client.set_responses(['{"score": 8.0, "reasoning": "Good content"}'])
    result = await mock_client.complete_structured("test", QualityScoreSchema)
    assert isinstance(result, QualityScoreSchema)
    assert result.score == 8.0
    assert result.passes_threshold is True


def test_mock_client_implements_protocol(mock_client):
    """Test that MockLLMClient conforms to LLMClient protocol."""
    assert isinstance(mock_client, LLMClient)


def test_create_llm_client_mock():
    """Test factory creates mock client."""
    client = create_llm_client("mock")
    assert isinstance(client, MockLLMClient)


def test_create_llm_client_unknown():
    """Test factory raises for unknown provider."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client("unknown_provider")


async def test_mock_client_retry_simulation(mock_client):
    """Simulate retry: first response is bad JSON, second is valid."""
    bad_json = "not valid json {{{"
    good_json = '{"passed": false, "reason": "low quality", "confidence": 0.8, "method": "ollama"}'
    mock_client.set_responses([bad_json, good_json])

    # First call with bad JSON
    r1 = await mock_client.complete("prompt")
    assert r1 == bad_json  # raw response

    # Second call with good JSON
    r2 = await mock_client.complete("prompt")
    assert json.loads(r2)["passed"] is False
