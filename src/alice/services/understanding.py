import json

import structlog

from alice.llm.protocol import LLMClient
from alice.prompts import prompt_manager
from alice.schemas.content import ContentUnderstandingSchema


class UnderstandingService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client
        self._logger = structlog.get_logger()

    async def process(
        self, title: str, text: str, language: str = "en"
    ) -> ContentUnderstandingSchema:
        prompt = prompt_manager.render_understanding(title=title, text=text, language=language)
        response = await self._llm_client.complete(prompt=prompt)
        parsed = self._parse_response(response)
        if parsed is None:
            retry_prompt = (
                "Your previous response was not valid JSON. "
                "Please respond with ONLY valid JSON matching the schema."
            )
            response = await self._llm_client.complete(prompt=f"{prompt}\n\n{retry_prompt}")
            parsed = self._parse_response(response)
            if parsed is None:
                raise ValueError("LLM returned invalid JSON after retry")

        self._logger.info(
            "understanding_complete",
            domains=parsed.domains,
            read_time=parsed.estimated_read_time,
        )
        return parsed

    def _parse_response(self, response: str) -> ContentUnderstandingSchema | None:
        import re

        text = response.strip()
        # Strip markdown code fences: ```json ... ``` or ``` ... ```
        # split("```", 2) → ['', 'json\n{...}\n', ''] so index [1] is the content
        if text.startswith("```") and text.count("```") >= 2:
            inner = text.split("```", 2)[1]
            # Drop the language hint line (e.g. "json\n")
            if "\n" in inner:
                first_line, rest = inner.split("\n", 1)
                text = rest.strip() if not first_line.strip().startswith("{") else inner.strip()
            else:
                text = inner.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fall back: extract first JSON object from response
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return None
            else:
                return None
        try:
            return ContentUnderstandingSchema.model_validate(data)
        except Exception:
            return None
