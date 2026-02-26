"""Unit tests for Search API endpoints.

TDD: tests written FIRST (RED), then implementation (GREEN).
Router does NOT exist yet — these tests FAIL at import (expected RED state).
Uses app.dependency_overrides for SearchService — no real Meilisearch required.
asyncio_mode = 'auto' in pyproject.toml → no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import meilisearch.errors
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alice.services.search import SearchService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_search_service():
    """Return a MagicMock SearchService with a sensible default search result."""
    svc = MagicMock(spec=SearchService)
    svc.search.return_value = {
        "hits": [{"id": "1", "title": "Test", "_formatted": {}}],
        "estimatedTotalHits": 1,
        "facetDistribution": {},
    }
    return svc


@pytest.fixture
def client(mock_search_service):
    """Create a minimal FastAPI app with the search router and mocked service."""
    from alice.api.v1.search import _get_search_service, router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[_get_search_service] = lambda: mock_search_service
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meili_error(
    message: str = "api error", code: str = "index_not_found"
) -> meilisearch.errors.MeilisearchApiError:
    """Build a MeilisearchApiError with a mock response."""
    response = MagicMock()
    response.status_code = 503
    response.text = json.dumps({"message": message, "code": code, "type": "system", "link": ""})
    return meilisearch.errors.MeilisearchApiError("error", response)


# ---------------------------------------------------------------------------
# GET /api/v1/search
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    def test_basic_search(self, client, mock_search_service):
        """GET /search?q=AI returns 200 with hits, total, query, offset, limit, facets."""
        resp = client.get("/api/v1/search?q=AI")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["hits"], list)
        assert data["total"] == 1
        assert data["query"] == "AI"
        assert data["offset"] == 0
        assert data["limit"] == 10
        assert isinstance(data["facets"], dict)

    def test_search_calls_service_with_query(self, client, mock_search_service):
        """GET /search?q=AI passes query to SearchService.search."""
        client.get("/api/v1/search?q=AI")

        mock_search_service.search.assert_called_once()
        call_kwargs = mock_search_service.search.call_args
        # query is the first positional arg
        assert call_kwargs[0][0] == "AI"

    def test_search_with_type_filter(self, client, mock_search_service):
        """GET /search?q=AI&type=deep_knowledge passes a filter string to the service."""
        client.get("/api/v1/search?q=AI&type=deep_knowledge")

        call_kwargs = mock_search_service.search.call_args[1]
        assert "filters" in call_kwargs
        assert "deep_knowledge" in call_kwargs["filters"]

    def test_search_with_min_score(self, client, mock_search_service):
        """GET /search?q=AI&min_score=7.0 passes a quality_score filter to the service."""
        client.get("/api/v1/search?q=AI&min_score=7.0")

        call_kwargs = mock_search_service.search.call_args[1]
        assert "filters" in call_kwargs
        assert "quality_score" in call_kwargs["filters"]

    def test_search_with_pagination(self, client, mock_search_service):
        """GET /search?q=AI&limit=5&offset=10 passes limit and offset correctly."""
        resp = client.get("/api/v1/search?q=AI&limit=5&offset=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 10
        # service receives the limit
        call_kwargs = mock_search_service.search.call_args[1]
        assert call_kwargs["limit"] == 5

    def test_search_empty_query_returns_400(self, client, mock_search_service):
        """GET /search?q= (empty string) returns 400 Bad Request."""
        resp = client.get("/api/v1/search?q=")

        assert resp.status_code == 400

    def test_search_missing_query_returns_422(self, client, mock_search_service):
        """GET /search without q parameter returns 422 Unprocessable Entity."""
        resp = client.get("/api/v1/search")

        assert resp.status_code == 422

    def test_search_meilisearch_error_returns_503(self, client, mock_search_service):
        """When SearchService.search raises MeilisearchApiError, returns 503."""
        mock_search_service.search.side_effect = _make_meili_error("search unavailable", "internal")

        resp = client.get("/api/v1/search?q=AI")

        assert resp.status_code == 503

    def test_search_response_hits_match_service_output(self, client, mock_search_service):
        """Hits in the response are exactly what the service returned."""
        mock_search_service.search.return_value = {
            "hits": [
                {"id": "42", "title": "Flash Attention", "_formatted": {}},
                {"id": "43", "title": "PagedAttention", "_formatted": {}},
            ],
            "estimatedTotalHits": 2,
            "facetDistribution": {"source": {"rss": 2}},
        }

        resp = client.get("/api/v1/search?q=attention")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hits"]) == 2
        assert data["total"] == 2
        assert data["facets"] == {"source": {"rss": 2}}

    def test_search_default_limit_is_10(self, client, mock_search_service):
        """GET /search?q=AI without explicit limit uses default limit of 10."""
        resp = client.get("/api/v1/search?q=AI")

        assert resp.status_code == 200
        assert resp.json()["limit"] == 10
        call_kwargs = mock_search_service.search.call_args[1]
        assert call_kwargs.get("limit", 10) == 10

    def test_search_default_offset_is_0(self, client, mock_search_service):
        """GET /search?q=AI without explicit offset uses default offset of 0."""
        resp = client.get("/api/v1/search?q=AI")

        assert resp.json()["offset"] == 0


# ---------------------------------------------------------------------------
# GET /api/v1/search/suggest
# ---------------------------------------------------------------------------


class TestSuggestEndpoint:
    def test_suggest_returns_suggestions(self, client, mock_search_service):
        """GET /search/suggest?q=py returns 200 with suggestions list and query."""
        mock_search_service.search.return_value = {
            "hits": [
                {"id": "1", "title": "Python tutorial"},
                {"id": "2", "title": "Python async programming"},
            ],
            "estimatedTotalHits": 2,
            "facetDistribution": {},
        }

        resp = client.get("/api/v1/search/suggest?q=py")

        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert "query" in data
        assert data["query"] == "py"
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) == 2
        assert "Python tutorial" in data["suggestions"]

    def test_suggest_empty_query_returns_empty(self, client, mock_search_service):
        """GET /search/suggest?q= (empty) returns 200 with empty suggestions."""
        resp = client.get("/api/v1/search/suggest?q=")

        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == []
        assert data["query"] == ""
        # service should NOT be called for empty query
        mock_search_service.search.assert_not_called()

    def test_suggest_with_custom_limit(self, client, mock_search_service):
        """GET /search/suggest?q=AI&limit=3 passes limit=3 to the service."""
        mock_search_service.search.return_value = {
            "hits": [{"id": "1", "title": "AI overview"}],
            "estimatedTotalHits": 1,
            "facetDistribution": {},
        }

        resp = client.get("/api/v1/search/suggest?q=AI&limit=3")

        assert resp.status_code == 200
        call_kwargs = mock_search_service.search.call_args[1]
        assert call_kwargs.get("limit") == 3

    def test_suggest_default_limit_is_5(self, client, mock_search_service):
        """GET /search/suggest?q=AI without limit uses default of 5."""
        mock_search_service.search.return_value = {
            "hits": [],
            "estimatedTotalHits": 0,
            "facetDistribution": {},
        }

        client.get("/api/v1/search/suggest?q=AI")

        call_kwargs = mock_search_service.search.call_args[1]
        assert call_kwargs.get("limit", 5) == 5

    def test_suggest_missing_query_returns_422(self, client, mock_search_service):
        """GET /search/suggest without q parameter returns 422."""
        resp = client.get("/api/v1/search/suggest")

        assert resp.status_code == 422

    def test_suggest_extracts_titles_from_hits(self, client, mock_search_service):
        """Suggestions are extracted from hit titles in service response."""
        mock_search_service.search.return_value = {
            "hits": [
                {"id": "10", "title": "Transformer architecture"},
                {"id": "11", "title": "Transformer variants"},
            ],
            "estimatedTotalHits": 2,
            "facetDistribution": {},
        }

        resp = client.get("/api/v1/search/suggest?q=trans")

        data = resp.json()
        assert "Transformer architecture" in data["suggestions"]
        assert "Transformer variants" in data["suggestions"]

    def test_suggest_calls_service_with_query(self, client, mock_search_service):
        """GET /search/suggest?q=ml passes query string to SearchService.search."""
        mock_search_service.search.return_value = {
            "hits": [],
            "estimatedTotalHits": 0,
            "facetDistribution": {},
        }

        client.get("/api/v1/search/suggest?q=ml")

        mock_search_service.search.assert_called_once()
        call_args = mock_search_service.search.call_args[0]
        assert call_args[0] == "ml"
