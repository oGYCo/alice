"""Ollama client for local LLM inference."""

import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    """Client for local Ollama LLM server."""

    def __init__(
        self, host: str = "http://host.docker.internal:11434", model: str = "qwen2.5:1.5b"
    ):
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = 60.0  # 60 second timeout for local model

    async def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._host}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._host}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json()["response"]

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
        temperature: float = 0.1,
    ) -> T:
        json_system = (
            system + "\n\nRespond ONLY with valid JSON."
            if system
            else "Respond ONLY with valid JSON."
        )
        text = await self.complete(prompt, system=json_system, temperature=temperature)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return response_model.model_validate(data)
