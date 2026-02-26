"""Meilisearch search service — index and query content items."""

from __future__ import annotations

import meilisearch
import structlog

from alice.models.content import Content

logger = structlog.get_logger(__name__)


class SearchService:
    """Wraps the Meilisearch client for content indexing and full-text search."""

    def __init__(self, url: str, api_key: str) -> None:
        self._client = meilisearch.Client(url, api_key)
        self._index_name = "content"

    def ensure_index(self) -> None:
        """Create content index with searchable/filterable/sortable attributes.

        create_index is idempotent — OK to call repeatedly on startup.
        """
        self._client.create_index(self._index_name, {"primaryKey": "id"})
        index = self._client.index(self._index_name)
        index.update_filterable_attributes(["content_type", "source", "pipeline_status"])
        index.update_sortable_attributes(["quality_score", "p_score", "created_at"])

    def index_content(self, content: Content) -> None:
        """Index a single Content ORM object into Meilisearch."""
        doc = {
            "id": str(content.id),
            "title": content.title,
            "summary": content.summary,
            "key_points": content.key_points,  # list[str] or None
            "source_url": content.source_url,
            "source": content.source,
            "content_type": content.metadata_.get("content_type") if content.metadata_ else None,
            "quality_score": content.quality_score,
            "p_score": content.p_score,
            "pipeline_status": content.pipeline_status,
            "created_at": content.created_at.isoformat() if content.created_at else None,
        }
        try:
            index = self._client.index(self._index_name)
            index.add_documents([doc])
        except meilisearch.errors.MeilisearchApiError:
            logger.error(
                "search_index_failed",
                content_id=str(content.id),
                title=content.title,
            )
            raise
        logger.info("search_indexed", content_id=str(content.id), title=content.title)

    def search(
        self,
        query: str,
        *,
        filters: str | None = None,
        limit: int = 10,
        highlight: bool = True,
    ) -> dict:
        """Full-text search with optional filters.

        Returns the raw Meilisearch search response dict.
        """
        params: dict = {"limit": limit}
        if filters:
            params["filter"] = filters
        if highlight:
            params["attributesToHighlight"] = ["title", "summary", "key_points"]
        try:
            index = self._client.index(self._index_name)
            result = index.search(query, params)
        except meilisearch.errors.MeilisearchApiError:
            logger.error("search_failed", query=query)
            raise
        logger.info("search_executed", query=query, hits=len(result.get("hits", [])))
        return result
