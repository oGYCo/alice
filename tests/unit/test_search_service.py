"""Unit tests for SearchService.

TDD: tests written FIRST (RED), then implementation (GREEN).
asyncio_mode = 'auto' — no @pytest.mark.asyncio needed.
SearchService is synchronous — no async/await needed.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import meilisearch
import pytest
from meilisearch.errors import MeilisearchApiError

from alice.models.content import Content
from alice.services.search import SearchService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meili_error(
    message: str = "api error", code: str = "index_not_found"
) -> MeilisearchApiError:
    """Build a MeilisearchApiError with a mock response."""
    response = MagicMock()
    response.status_code = 404
    response.text = json.dumps(
        {"message": message, "code": code, "type": "invalid_request", "link": ""}
    )
    return MeilisearchApiError("error", response)


def _make_content(**kwargs) -> MagicMock:
    """Build a MagicMock that looks like a Content ORM object."""
    c = MagicMock(spec=Content)
    c.id = kwargs.get("id", uuid.uuid4())
    c.title = kwargs.get("title", "Test Title")
    c.summary = kwargs.get("summary", "Test summary")
    c.key_points = kwargs.get("key_points", ["point 1"])
    c.source_url = kwargs.get("source_url", "https://example.com")
    c.source = kwargs.get("source", "rss")
    c.metadata_ = kwargs.get("metadata_", {"content_type": "blog"})
    c.quality_score = kwargs.get("quality_score", 7.5)
    c.p_score = kwargs.get("p_score", 0.85)
    c.pipeline_status = kwargs.get("pipeline_status", "indexed")
    c.created_at = kwargs.get("created_at", datetime(2026, 2, 26, tzinfo=UTC))
    return c


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Return (mocked meilisearch.Client, mocked index)."""
    client = MagicMock(spec=meilisearch.Client)
    mock_index = MagicMock()
    client.index.return_value = mock_index
    return client, mock_index


@pytest.fixture
def search_service(mock_client):
    """Instantiate SearchService with a patched meilisearch.Client."""
    client, _ = mock_client
    with patch("meilisearch.Client", return_value=client):
        service = SearchService("http://localhost:7700", "masterkey")
    return service, mock_client


# ---------------------------------------------------------------------------
# ensure_index tests
# ---------------------------------------------------------------------------


class TestEnsureIndex:
    def test_ensure_index_creates_index(self, search_service):
        """ensure_index calls create_index with correct name and primaryKey."""
        service, (client, _) = search_service

        service.ensure_index()

        client.create_index.assert_called_once_with("content", {"primaryKey": "id"})

    def test_ensure_index_sets_filterable_attributes(self, search_service):
        """ensure_index calls update_filterable_attributes with the expected list."""
        service, (client, mock_index) = search_service

        service.ensure_index()

        mock_index.update_filterable_attributes.assert_called_once_with(
            ["content_type", "source", "pipeline_status"]
        )

    def test_ensure_index_sets_sortable_attributes(self, search_service):
        """ensure_index calls update_sortable_attributes with the expected list."""
        service, (client, mock_index) = search_service

        service.ensure_index()

        mock_index.update_sortable_attributes.assert_called_once_with(
            ["quality_score", "p_score", "created_at"]
        )


# ---------------------------------------------------------------------------
# index_content tests
# ---------------------------------------------------------------------------


class TestIndexContent:
    def test_index_content_sends_correct_document(self, search_service):
        """index_content calls add_documents with a dict containing all expected fields."""
        service, (client, mock_index) = search_service
        content = _make_content(
            title="Flash Attention",
            summary="Fast attention mechanism",
            source_url="https://arxiv.org/abs/123",
            source="rss",
            quality_score=9.0,
            p_score=0.92,
            pipeline_status="indexed",
        )
        content_id = content.id

        service.index_content(content)

        mock_index.add_documents.assert_called_once()
        docs = mock_index.add_documents.call_args[0][0]
        assert len(docs) == 1
        doc = docs[0]

        assert doc["id"] == str(content_id)
        assert doc["title"] == "Flash Attention"
        assert doc["summary"] == "Fast attention mechanism"
        assert doc["key_points"] == ["point 1"]
        assert doc["source_url"] == "https://arxiv.org/abs/123"
        assert doc["source"] == "rss"
        assert doc["quality_score"] == 9.0
        assert doc["p_score"] == 0.92
        assert doc["pipeline_status"] == "indexed"

    def test_index_content_content_type_from_metadata(self, search_service):
        """index_content extracts content_type from metadata_.get('content_type')."""
        service, (client, mock_index) = search_service
        content = _make_content(metadata_={"content_type": "arxiv"})

        service.index_content(content)

        docs = mock_index.add_documents.call_args[0][0]
        assert docs[0]["content_type"] == "arxiv"

    def test_index_content_content_type_none_when_missing(self, search_service):
        """index_content sets content_type=None when key absent from metadata_."""
        service, (client, mock_index) = search_service
        content = _make_content(metadata_={"other_key": "value"})

        service.index_content(content)

        docs = mock_index.add_documents.call_args[0][0]
        assert docs[0]["content_type"] is None

    def test_index_content_created_at_iso_format(self, search_service):
        """index_content stores created_at as ISO 8601 string."""
        service, (client, mock_index) = search_service
        created = datetime(2026, 2, 26, 12, 0, 0, tzinfo=UTC)
        content = _make_content(created_at=created)

        service.index_content(content)

        docs = mock_index.add_documents.call_args[0][0]
        assert docs[0]["created_at"] == created.isoformat()

    def test_index_content_raises_on_meilisearch_error(self, search_service):
        """index_content re-raises MeilisearchApiError from add_documents."""
        service, (client, mock_index) = search_service
        mock_index.add_documents.side_effect = _make_meili_error("index unavailable")
        content = _make_content()

        with pytest.raises(MeilisearchApiError):
            service.index_content(content)


# ---------------------------------------------------------------------------
# search tests
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_basic(self, search_service):
        """search('query') calls index.search with limit=10 by default."""
        service, (client, mock_index) = search_service
        mock_index.search.return_value = {"hits": []}

        service.search("machine learning")

        mock_index.search.assert_called_once()
        call_query, call_params = mock_index.search.call_args[0]
        assert call_query == "machine learning"
        assert call_params["limit"] == 10

    def test_search_with_filters(self, search_service):
        """Passing filters= includes {'filter': ...} in search params."""
        service, (client, mock_index) = search_service
        mock_index.search.return_value = {"hits": []}

        service.search("transformers", filters="source=rss")

        _, call_params = mock_index.search.call_args[0]
        assert call_params["filter"] == "source=rss"

    def test_search_no_filter_when_not_provided(self, search_service):
        """When filters=None, 'filter' key is absent from search params."""
        service, (client, mock_index) = search_service
        mock_index.search.return_value = {"hits": []}

        service.search("attention")

        _, call_params = mock_index.search.call_args[0]
        assert "filter" not in call_params

    def test_search_custom_limit(self, search_service):
        """Passing limit= overrides the default limit of 10."""
        service, (client, mock_index) = search_service
        mock_index.search.return_value = {"hits": []}

        service.search("rag", limit=25)

        _, call_params = mock_index.search.call_args[0]
        assert call_params["limit"] == 25

    def test_search_highlight_enabled_by_default(self, search_service):
        """highlight=True (default) includes attributesToHighlight in params."""
        service, (client, mock_index) = search_service
        mock_index.search.return_value = {"hits": []}

        service.search("attention")

        _, call_params = mock_index.search.call_args[0]
        assert "attributesToHighlight" in call_params

    def test_search_highlight_disabled(self, search_service):
        """highlight=False omits attributesToHighlight from params."""
        service, (client, mock_index) = search_service
        mock_index.search.return_value = {"hits": []}

        service.search("attention", highlight=False)

        _, call_params = mock_index.search.call_args[0]
        assert "attributesToHighlight" not in call_params

    def test_search_returns_result(self, search_service):
        """search returns the raw dict from index.search."""
        service, (client, mock_index) = search_service
        expected = {"hits": [{"id": "abc", "title": "Test"}], "query": "test"}
        mock_index.search.return_value = expected

        result = service.search("test")

        assert result is expected

    def test_search_raises_on_meilisearch_error(self, search_service):
        """search re-raises MeilisearchApiError from index.search."""
        service, (client, mock_index) = search_service
        mock_index.search.side_effect = _make_meili_error("search failed", "internal")

        with pytest.raises(MeilisearchApiError):
            service.search("broken query")
