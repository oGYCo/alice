from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import arxiv  # type: ignore[import-untyped]

from ..schemas.content import RawContentSchema
from ..schemas.source import SourceConfigSchema
from .base import BaseConnector


class ArxivConnector(BaseConnector):
    async def fetch(self, config: SourceConfigSchema) -> list[RawContentSchema]:
        config_map = dict(config.config)
        max_results_value = config_map.get("max_results", 20)
        max_results = max_results_value if isinstance(max_results_value, int) else 20

        def _fetch_blocking() -> list[arxiv.Result]:
            client = arxiv.Client()
            search = arxiv.Search(
                query=config.url,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
            )
            return list(client.results(search))

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _fetch_blocking)

        fetched_at = datetime.now(UTC)
        items: list[RawContentSchema] = []
        for result in results:
            items.append(
                RawContentSchema(
                    source="arxiv",
                    source_url=result.entry_id,
                    source_id=result.entry_id,
                    title=result.title,
                    raw_text=result.summary,
                    author=", ".join(a.name for a in result.authors),
                    published_at=result.published,
                    fetched_at=fetched_at,
                    metadata={"pdf_url": result.pdf_url, "categories": result.categories},
                )
            )
        return items
