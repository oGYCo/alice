"""Unit tests for Source CRUD API endpoints.

Tests all 4 endpoints: POST, GET, PUT /sources/{id}, DELETE /sources/{id}.
Uses app.dependency_overrides for SourceService — no real DB or broker required.
asyncio_mode = 'auto' in pyproject.toml → no @pytest.mark.asyncio needed.
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from alice.main import create_app
from alice.models.source import Source, SourceType
from alice.schemas.source import SourceConfigSchema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(**kwargs) -> MagicMock:
    """Create a mock Source ORM object."""
    defaults = dict(
        id=1,
        name="Test RSS",
        type=SourceType.rss,
        url="https://example.com/feed.xml",
        config={},
        is_active=True,
        fetch_interval_minutes=30,
        last_fetched_at=None,
        created_at=None,
        updated_at=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Source)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_mock_service() -> AsyncMock:
    """Create a mock SourceService."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# POST /api/v1/sources
# ---------------------------------------------------------------------------


class TestCreateSource:
    def test_create_source_returns_201(self):
        """POST /sources returns 201 with created source."""
        source = _make_source(id=1, name="My RSS", type=SourceType.rss)
        mock_svc = _make_mock_service()
        mock_svc.create.return_value = source

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/sources",
                    json={
                        "name": "My RSS",
                        "url": "https://example.com/feed.xml",
                        "type": "rss",
                        "config": {},
                        "enabled": True,
                        "fetch_interval_minutes": 30,
                    },
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "My RSS"

    def test_create_source_calls_service_create(self):
        """POST /sources invokes svc.create with the config schema."""
        source = _make_source()
        mock_svc = _make_mock_service()
        mock_svc.create.return_value = source

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                client.post(
                    "/api/v1/sources",
                    json={
                        "name": "Test",
                        "url": "https://example.com/feed.xml",
                        "type": "rss",
                        "config": {},
                    },
                )

        mock_svc.create.assert_called_once()
        call_arg = mock_svc.create.call_args[0][0]
        assert isinstance(call_arg, SourceConfigSchema)
        assert call_arg.name == "Test"

    def test_create_source_invalid_type_returns_422(self):
        """POST /sources with invalid type returns 422."""
        app = create_app()

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/sources",
                json={
                    "name": "Test",
                    "url": "https://example.com/feed.xml",
                    "type": "twitter",  # invalid
                    "config": {},
                },
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/sources
# ---------------------------------------------------------------------------


class TestListSources:
    def test_list_sources_returns_200(self):
        """GET /sources returns 200 with list of sources."""
        sources = [_make_source(id=1), _make_source(id=2, name="arXiv")]
        mock_svc = _make_mock_service()
        mock_svc.list_active.return_value = sources

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.get("/api/v1/sources")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 1

    def test_list_sources_empty_returns_empty_list(self):
        """GET /sources with no sources returns empty list."""
        mock_svc = _make_mock_service()
        mock_svc.list_active.return_value = []

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.get("/api/v1/sources")

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# PUT /api/v1/sources/{id}
# ---------------------------------------------------------------------------


class TestUpdateSource:
    def test_update_source_returns_200(self):
        """PUT /sources/{id} returns 200 with updated source."""
        updated = _make_source(id=5, name="Updated", fetch_interval_minutes=60)
        mock_svc = _make_mock_service()
        mock_svc.update_source.return_value = updated

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/v1/sources/5",
                    json={"fetch_interval_minutes": 60},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 5
        assert data["fetch_interval_minutes"] == 60

    def test_update_source_not_found_returns_404(self):
        """PUT /sources/{id} returns 404 when source not found."""
        mock_svc = _make_mock_service()
        mock_svc.update_source.side_effect = ValueError("Source 99 not found")

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/v1/sources/99",
                    json={"fetch_interval_minutes": 60},
                )

        assert resp.status_code == 404

    def test_update_source_calls_service(self):
        """PUT /sources/{id} passes correct kwargs to svc.update_source."""
        updated = _make_source(id=3, is_active=False)
        mock_svc = _make_mock_service()
        mock_svc.update_source.return_value = updated

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                client.put(
                    "/api/v1/sources/3",
                    json={"enabled": False},
                )

        mock_svc.update_source.assert_called_once()
        call_args = mock_svc.update_source.call_args
        assert call_args[0][0] == 3  # source_id

    def test_update_source_partial_fields(self):
        """PUT /sources/{id} accepts partial updates (only changed fields)."""
        updated = _make_source(id=1, name="New Name")
        mock_svc = _make_mock_service()
        mock_svc.update_source.return_value = updated

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/v1/sources/1",
                    json={"name": "New Name"},
                )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/v1/sources/{id}
# ---------------------------------------------------------------------------


class TestDeleteSource:
    def test_delete_source_returns_204(self):
        """DELETE /sources/{id} returns 204 No Content."""
        mock_svc = _make_mock_service()
        mock_svc.delete_source.return_value = None

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.delete("/api/v1/sources/1")

        assert resp.status_code == 204
        assert resp.content == b""

    def test_delete_source_not_found_returns_404(self):
        """DELETE /sources/{id} returns 404 when source not found."""
        mock_svc = _make_mock_service()
        mock_svc.delete_source.side_effect = ValueError("Source 99 not found")

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                resp = client.delete("/api/v1/sources/99")

        assert resp.status_code == 404

    def test_delete_source_calls_service(self):
        """DELETE /sources/{id} calls svc.delete_source with correct id."""
        mock_svc = _make_mock_service()
        mock_svc.delete_source.return_value = None

        app = create_app()

        with patch("alice.api.v1.sources._get_source_service", return_value=mock_svc):
            with TestClient(app) as client:
                client.delete("/api/v1/sources/7")

        mock_svc.delete_source.assert_called_once_with(7)
