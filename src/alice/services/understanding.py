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
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return None
        return ContentUnderstandingSchema.model_validate(data)
