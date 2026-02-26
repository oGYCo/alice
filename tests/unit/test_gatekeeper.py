import importlib
import json
from pathlib import Path
from typing import Protocol, cast


class GatekeeperDecisionLike(Protocol):
    passed: bool
    reason: str
    confidence: float
    method: str


class GatekeeperServiceLike(Protocol):
    def __call__(self, llm_client: object) -> "GatekeeperServiceLike": ...

    async def evaluate(
        self, content_text: str, content_url: str = ""
    ) -> GatekeeperDecisionLike: ...


class MockLLMClientLike(Protocol):
    def set_responses(self, responses: list[str]) -> None: ...

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str: ...


class OllamaClientLike(Protocol):
    async def is_available(self) -> bool: ...

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str: ...


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "llm_responses"


def _load_fixture_response(name: str) -> str:
    payload = cast(dict[str, str], json.loads((FIXTURES_DIR / name).read_text()))
    return payload["response"]


def _load_gatekeeper_service_type() -> GatekeeperServiceLike:
    return cast(
        GatekeeperServiceLike,
        importlib.import_module("alice.services.gatekeeper").GatekeeperService,
    )


def _load_mock_llm_client_type() -> type[MockLLMClientLike]:
    return cast(
        type[MockLLMClientLike],
        importlib.import_module("alice.llm.mock").MockLLMClient,
    )


def _load_ollama_client_type() -> type[OllamaClientLike]:
    return cast(
        type[OllamaClientLike],
        importlib.import_module("alice.llm.ollama").OllamaClient,
    )


def _load_gatekeeper_decision_type() -> type[GatekeeperDecisionLike]:
    return cast(
        type[GatekeeperDecisionLike],
        importlib.import_module("alice.schemas.gatekeeper").GatekeeperDecision,
    )


async def test_gatekeeper_llm_passes_content():
    MockLLMClient = _load_mock_llm_client_type()  # noqa: N806
    GatekeeperService = _load_gatekeeper_service_type()  # noqa: N806
    GatekeeperDecision = _load_gatekeeper_decision_type()  # noqa: N806

    client = MockLLMClient()
    client.set_responses([_load_fixture_response("gatekeeper_pass.json")])
    service = GatekeeperService(cast(object, client))

    decision = await service.evaluate("Long enough content for evaluation")

    assert isinstance(decision, GatekeeperDecision)
    assert decision.passed is True
    assert decision.method == "ollama"


async def test_gatekeeper_llm_rejects_content():
    MockLLMClient = _load_mock_llm_client_type()  # noqa: N806
    GatekeeperService = _load_gatekeeper_service_type()  # noqa: N806

    client = MockLLMClient()
    client.set_responses([_load_fixture_response("gatekeeper_reject.json")])
    service = GatekeeperService(cast(object, client))

    decision = await service.evaluate("Long enough content for evaluation")

    assert decision.passed is False
    assert decision.method == "ollama"


async def test_gatekeeper_falls_back_when_ollama_unavailable():
    OllamaClient = _load_ollama_client_type()  # noqa: N806
    GatekeeperService = _load_gatekeeper_service_type()  # noqa: N806

    class UnavailableOllamaClient(OllamaClient):
        async def is_available(self) -> bool:  # type: ignore[override]
            return False

        async def complete(
            self,
            prompt: str,
            system: str = "",
            temperature: float = 0.7,
            max_tokens: int = 2000,
        ) -> str:  # type: ignore[override]
            _ = prompt, system, temperature, max_tokens
            raise AssertionError("LLM should not be called when unavailable")

    service = GatekeeperService(cast(object, UnavailableOllamaClient()))
    decision = await service.evaluate("x" * 120)

    assert decision.passed is True
    assert decision.method == "rule-based"


async def test_gatekeeper_rule_based_rejects_short_text():
    MockLLMClient = _load_mock_llm_client_type()  # noqa: N806
    GatekeeperService = _load_gatekeeper_service_type()  # noqa: N806

    class FailingClient(MockLLMClient):
        def set_responses(self, responses: list[str]) -> None:
            _ = responses

        async def complete(
            self,
            prompt: str,
            system: str = "",
            temperature: float = 0.7,
            max_tokens: int = 2000,
        ) -> str:  # type: ignore[override]
            _ = prompt, system, temperature, max_tokens
            raise RuntimeError("LLM unavailable")

    service = GatekeeperService(cast(object, FailingClient()))

    decision = await service.evaluate("Too short")

    assert decision.passed is False
    assert decision.method == "rule-based"


async def test_gatekeeper_rule_based_passes_long_text():
    MockLLMClient = _load_mock_llm_client_type()  # noqa: N806
    GatekeeperService = _load_gatekeeper_service_type()  # noqa: N806

    class FailingClient(MockLLMClient):
        def set_responses(self, responses: list[str]) -> None:
            _ = responses

        async def complete(
            self,
            prompt: str,
            system: str = "",
            temperature: float = 0.7,
            max_tokens: int = 2000,
        ) -> str:  # type: ignore[override]
            _ = prompt, system, temperature, max_tokens
            raise RuntimeError("LLM unavailable")

    service = GatekeeperService(cast(object, FailingClient()))
    decision = await service.evaluate("Content with enough substance. " * 10)

    assert decision.passed is True
    assert decision.confidence == 0.5
    assert decision.method == "rule-based"
