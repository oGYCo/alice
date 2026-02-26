"""Mock LLM client for testing — returns fixture data."""

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "llm_responses"


class MockLLMClient:
    """Mock LLM client that returns predefined fixture responses."""

    def __init__(self, fixture_name: str = "default"):
        self._fixture_name = fixture_name
        self._call_count = 0
        self._responses: list[str] = []

    def set_responses(self, responses: list[str]) -> None:
        """Set a sequence of responses to return in order."""
        self._responses = responses
        self._call_count = 0

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        if self._responses:
            idx = min(self._call_count, len(self._responses) - 1)
            self._call_count += 1
            return self._responses[idx]

        # Load from fixture file
        fixture_path = FIXTURES_DIR / f"{self._fixture_name}.json"
        if fixture_path.exists():
            with open(fixture_path) as f:
                data = json.load(f)
            return data.get("response", '{"status": "ok"}')

        return '{"status": "ok", "message": "mock response"}'

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
        temperature: float = 0.1,
    ) -> T:
        text = await self.complete(prompt, system=system)
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        data = json.loads(text)
        return response_model.model_validate(data)
