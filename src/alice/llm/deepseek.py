"""DeepSeek LLM client using OpenAI-compatible API."""

import asyncio
import json
import logging
from typing import TypeVar

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
RETRY_DELAYS = [1, 5, 30]  # seconds


class DeepSeekClient:
    """DeepSeek API client using OpenAI SDK."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=600.0,  # 10 minute timeout for long LLM calls
            max_retries=0,  # We handle retries manually
        )

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except (APITimeoutError, RateLimitError) as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        f"LLM call failed (attempt {attempt + 1}): {e}. Retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except APIError:
                raise  # Don't retry on API errors

        raise RuntimeError("Should not reach here")

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
        temperature: float = 0.1,
    ) -> T:
        # Add JSON instruction to system prompt
        json_system = (
            system + "\n\nRespond ONLY with valid JSON."
            if system
            else "Respond ONLY with valid JSON."
        )

        for attempt in range(MAX_RETRIES):
            text = await self.complete(prompt, system=json_system, temperature=temperature)
            try:
                # Strip markdown code blocks if present
                text = text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                data = json.loads(text)
                return response_model.model_validate(data)
            except (json.JSONDecodeError, Exception) as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Failed to parse structured response (attempt {attempt + 1}): {e}"
                    )
                    prompt = prompt + "\n\nIMPORTANT: Output ONLY valid JSON, nothing else."
                else:
                    raise ValueError(
                        f"Failed to parse LLM response as {response_model.__name__}: {e}"
                    ) from e

        raise RuntimeError("Should not reach here")
