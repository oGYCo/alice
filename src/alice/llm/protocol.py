"""LLM client protocol — all LLM implementations must conform to this interface."""

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for all LLM clients. Use this for type hints everywhere."""

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send a completion request and return the text response."""
        ...

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
        temperature: float = 0.1,
    ) -> T:
        """Send a completion request and parse into a Pydantic model."""
        ...
