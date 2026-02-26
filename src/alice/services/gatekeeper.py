import importlib
import json
import string
from typing import Protocol, cast, runtime_checkable


class LLMClient(Protocol):
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str: ...


@runtime_checkable
class OllamaClientLike(Protocol):
    async def is_available(self) -> bool: ...


class LoggerLike(Protocol):
    def info(self, event: str, **kwargs: object) -> None: ...


class StructlogModule(Protocol):
    def get_logger(self) -> LoggerLike: ...


class PromptManagerLike(Protocol):
    def render(self, template_name: str, **kwargs: object) -> str: ...


class GatekeeperDecisionLike(Protocol):
    passed: bool
    reason: str
    confidence: float
    method: str


class GatekeeperDecisionModel(Protocol):
    def __call__(self, **kwargs: object) -> GatekeeperDecisionLike: ...

    @classmethod
    def model_validate(cls, data: object) -> GatekeeperDecisionLike: ...


class GatekeeperService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client: LLMClient = llm_client
        structlog_module = cast(StructlogModule, cast(object, importlib.import_module("structlog")))
        self._logger: LoggerLike = structlog_module.get_logger()
        self._prompt_manager: PromptManagerLike = cast(
            PromptManagerLike, importlib.import_module("alice.prompts").prompt_manager
        )
        self._decision_model: GatekeeperDecisionModel = cast(
            GatekeeperDecisionModel,
            importlib.import_module("alice.schemas.gatekeeper").GatekeeperDecision,
        )

    async def evaluate(self, content_text: str, content_url: str = "") -> GatekeeperDecisionLike:
        use_fallback = await self._ollama_unavailable()
        if use_fallback:
            decision = self._rule_based_decision(content_text)
            self._logger.info(
                "gatekeeper_decision",
                passed=decision.passed,
                method=decision.method,
                confidence=decision.confidence,
            )
            return decision

        prompt = self._prompt_manager.render(
            "gatekeeper",
            title="Unknown",
            text=content_text,
            source=content_url,
        )
        try:
            response = await self._llm_client.complete(prompt=prompt)
            decision = self._parse_response(response)
        except Exception:
            decision = self._rule_based_decision(content_text)

        self._logger.info(
            "gatekeeper_decision",
            passed=decision.passed,
            method=decision.method,
            confidence=decision.confidence,
        )
        return decision

    async def _ollama_unavailable(self) -> bool:
        if isinstance(self._llm_client, OllamaClientLike):
            return not await self._llm_client.is_available()
        return False

    def _parse_response(self, response: str) -> GatekeeperDecisionLike:
        try:
            data = cast(dict[str, object], json.loads(response.strip()))
        except json.JSONDecodeError:
            retry_prompt = (
                "Your previous response was not valid JSON. "
                "Please respond with ONLY valid JSON matching the schema."
            )
            raise ValueError(retry_prompt)
        if "method" not in data:
            data["method"] = "ollama"
        return self._decision_model.model_validate(data)

    def _rule_based_decision(self, content_text: str) -> GatekeeperDecisionLike:
        stripped = content_text.strip()
        total_len = len(content_text)
        non_space = sum(1 for ch in content_text if not ch.isspace())
        alpha_numeric = sum(1 for ch in content_text if ch.isalnum())
        punctuation = sum(1 for ch in content_text if ch in string.punctuation)

        if len(stripped) < 100:
            decision = self._decision_model(
                passed=False,
                reason="rule-based: too short",
                confidence=0.5,
                method="rule-based",
            )
        elif total_len == 0 or non_space == 0:
            decision = self._decision_model(
                passed=False,
                reason="rule-based: mostly whitespace",
                confidence=0.5,
                method="rule-based",
            )
        elif non_space / max(total_len, 1) < 0.1:
            decision = self._decision_model(
                passed=False,
                reason="rule-based: mostly whitespace",
                confidence=0.5,
                method="rule-based",
            )
        elif punctuation / max(alpha_numeric + punctuation, 1) > 0.9:
            decision = self._decision_model(
                passed=False,
                reason="rule-based: mostly punctuation",
                confidence=0.5,
                method="rule-based",
            )
        else:
            decision = self._decision_model(
                passed=True,
                reason="rule-based fallback",
                confidence=0.5,
                method="rule-based",
            )

        return decision
