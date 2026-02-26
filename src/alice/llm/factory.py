"""Factory function to create LLM clients."""

from alice.config import settings

from .deepseek import DeepSeekClient
from .mock import MockLLMClient
from .ollama import OllamaClient
from .protocol import LLMClient


def create_llm_client(provider: str = "deepseek") -> LLMClient:
    """Create an LLM client for the given provider."""
    if provider == "deepseek":
        return DeepSeekClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    elif provider == "ollama":
        return OllamaClient(host=settings.OLLAMA_HOST)
    elif provider == "mock":
        return MockLLMClient()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
