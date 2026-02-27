"""Unit tests for feedback API endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from alice.db import get_db
from alice.main import create_app


def _app_with_mock_session(mock_session: AsyncMock):
    app = create_app()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    return app


def test_create_feedback_maps_positive_to_valuable_learned():
    mock_session = MagicMock()
    content_exists_result = MagicMock()
    content_exists_result.scalar_one_or_none.return_value = 123
    mock_session.execute = AsyncMock(return_value=content_exists_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    async def _refresh(obj):
        obj.id = 10
        obj.created_at = datetime(2026, 1, 1, tzinfo=UTC)

    mock_session.refresh = AsyncMock(side_effect=_refresh)

    app = _app_with_mock_session(mock_session)
    with patch(
        "alice.api.v1.feedback._get_or_create_user",
        AsyncMock(return_value=MagicMock()),
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/feedback",
                json={"content_id": 123, "feedback_type": "positive"},
                headers={"X-API-Key": "alicesecret"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["content_id"] == 123
    assert data["user_id"] == 1
    assert data["type"] == "valuable_learned"


def test_create_feedback_returns_404_when_content_not_found():
    mock_session = MagicMock()
    no_content_result = MagicMock()
    no_content_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=no_content_result)

    app = _app_with_mock_session(mock_session)
    with patch(
        "alice.api.v1.feedback._get_or_create_user",
        AsyncMock(return_value=MagicMock()),
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/feedback",
                json={"content_id": 999999, "feedback_type": "seen"},
                headers={"X-API-Key": "alicesecret"},
            )

    assert response.status_code == 404


def test_create_feedback_accepts_legacy_feedback_names():
    mock_session = MagicMock()
    content_exists_result = MagicMock()
    content_exists_result.scalar_one_or_none.return_value = 321
    mock_session.execute = AsyncMock(return_value=content_exists_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    async def _refresh(obj):
        obj.id = 11
        obj.created_at = datetime(2026, 1, 2, tzinfo=UTC)

    mock_session.refresh = AsyncMock(side_effect=_refresh)

    app = _app_with_mock_session(mock_session)
    with patch(
        "alice.api.v1.feedback._get_or_create_user",
        AsyncMock(return_value=MagicMock()),
    ):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/feedback",
                json={
                    "content_id": 321,
                    "user_id": 7,
                    "feedback_type": "not_valuable",
                },
                headers={"X-API-Key": "alicesecret"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == 7
    assert data["type"] == "not_valuable"
