"""Unit tests for ContentStorageService and SourceService.

Uses AsyncMock for DB session — no real DB required.
asyncio_mode = 'auto' in pyproject.toml → no @pytest.mark.asyncio needed.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.content import Content, PipelineStatus
from alice.models.source import Source, SourceType
from alice.schemas.content import RawContentSchema
from alice.schemas.source import SourceConfigSchema
from alice.services.source_service import SourceService
from alice.services.storage import ContentStorageService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> MagicMock:
    defaults = dict(
        id=1,
        source="rss",
        source_url="https://example.com/article",
        pipeline_status=PipelineStatus.fetched,
        pipeline_error=None,
        quality_score=None,
        summary=None,
        key_points=None,
        domains=None,
        estimated_read_time=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Content)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_source(**kwargs) -> MagicMock:
    defaults = dict(
        id=1,
        type=SourceType.rss,
        name="Test Feed",
        url="https://example.com/feed.xml",
        config={},
        is_active=True,
        last_fetched_at=None,
        fetch_interval_minutes=30,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Source)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# ContentStorageService — store_raw
# ---------------------------------------------------------------------------


class TestContentStorageServiceStoreRaw:
    async def test_store_raw_inserts_new_content(self):
        """New URL → inserts Content row, returns it."""
        session = _make_session()
        # No existing content → scalar returns None
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        raw = RawContentSchema(
            source="rss",
            source_url="https://example.com/article-1",
            title="Test Article",
        )

        svc = ContentStorageService(session)
        await svc.store_raw(raw)

        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    async def test_store_raw_deduplicates_existing_url(self):
        """Existing URL → returns existing content, does NOT insert."""
        session = _make_session()
        existing = _make_content(source_url="https://example.com/article-1")

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        raw = RawContentSchema(
            source="rss",
            source_url="https://example.com/article-1",
        )
        svc = ContentStorageService(session)
        returned = await svc.store_raw(raw)

        session.add.assert_not_called()
        session.commit.assert_not_called()
        assert returned is existing

    async def test_store_raw_normalizes_url_trailing_slash(self):
        """Trailing slash stripped before dedup check."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        raw = RawContentSchema(
            source="rss",
            source_url="https://example.com/article-1/",
        )
        svc = ContentStorageService(session)
        await svc.store_raw(raw)

        # The Content passed to session.add must have normalized URL
        added_obj = session.add.call_args[0][0]
        assert not added_obj.source_url.endswith("/")

    async def test_store_raw_normalizes_url_www(self):
        """www. stripped from host."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        raw = RawContentSchema(
            source="rss",
            source_url="https://www.example.com/article",
        )
        svc = ContentStorageService(session)
        await svc.store_raw(raw)

        added_obj = session.add.call_args[0][0]
        assert "www." not in added_obj.source_url

    async def test_store_raw_normalizes_utm_params(self):
        """utm_* query params stripped."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        raw = RawContentSchema(
            source="rss",
            source_url="https://example.com/article?utm_source=email&utm_medium=social",
        )
        svc = ContentStorageService(session)
        await svc.store_raw(raw)

        added_obj = session.add.call_args[0][0]
        assert "utm_source" not in added_obj.source_url
        assert "utm_medium" not in added_obj.source_url

    async def test_store_raw_initial_status_is_fetched(self):
        """Content inserted with pipeline_status = fetched."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        raw = RawContentSchema(source="rss", source_url="https://example.com/x")
        svc = ContentStorageService(session)
        await svc.store_raw(raw)

        added_obj = session.add.call_args[0][0]
        assert added_obj.pipeline_status == PipelineStatus.fetched


# ---------------------------------------------------------------------------
# ContentStorageService — get_by_id
# ---------------------------------------------------------------------------


class TestContentStorageServiceGetById:
    async def test_get_by_id_returns_content(self):
        session = _make_session()
        content = _make_content(id=42)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = content
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        found = await svc.get_by_id(42)
        assert found is content

    async def test_get_by_id_returns_none_when_missing(self):
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        found = await svc.get_by_id(999)
        assert found is None


# ---------------------------------------------------------------------------
# ContentStorageService — update_pipeline_status
# ---------------------------------------------------------------------------


class TestContentStorageServiceUpdatePipelineStatus:
    async def test_update_pipeline_status_commits(self):
        session = _make_session()
        content = _make_content(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = content
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        await svc.update_pipeline_status(1, PipelineStatus.gatekept)

        assert content.pipeline_status == PipelineStatus.gatekept
        session.commit.assert_called_once()

    async def test_update_pipeline_status_sets_error(self):
        session = _make_session()
        content = _make_content(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = content
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        await svc.update_pipeline_status(1, PipelineStatus.failed, error="boom")

        assert content.pipeline_error == "boom"
        session.commit.assert_called_once()

    async def test_update_pipeline_status_raises_on_missing(self):
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        with pytest.raises(ValueError, match="Content.*not found"):
            await svc.update_pipeline_status(999, PipelineStatus.gatekept)


# ---------------------------------------------------------------------------
# ContentStorageService — update_understanding
# ---------------------------------------------------------------------------


class TestContentStorageServiceUpdateUnderstanding:
    async def test_update_understanding_sets_fields(self):
        session = _make_session()
        content = _make_content(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = content
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        await svc.update_understanding(
            1,
            summary="Great article",
            key_points=["point1", "point2"],
            domains=["AI", "ML"],
            read_time=5,
        )

        assert content.summary == "Great article"
        assert content.key_points == ["point1", "point2"]
        assert content.domains == ["AI", "ML"]
        assert content.estimated_read_time == 5
        assert content.pipeline_status == PipelineStatus.understood
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# ContentStorageService — update_score
# ---------------------------------------------------------------------------


class TestContentStorageServiceUpdateScore:
    async def test_update_score_sets_fields(self):
        session = _make_session()
        content = _make_content(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = content
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        await svc.update_score(1, score=8.5, reasoning="Very relevant")

        assert content.quality_score == 8.5
        assert content.pipeline_status == PipelineStatus.scored
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# ContentStorageService — get_pending
# ---------------------------------------------------------------------------


class TestContentStorageServiceGetPending:
    async def test_get_pending_returns_list(self):
        session = _make_session()
        items = [_make_content(id=i) for i in range(3)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = items
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        pending = await svc.get_pending(PipelineStatus.fetched)
        assert len(pending) == 3

    async def test_get_pending_respects_limit(self):
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        await svc.get_pending(PipelineStatus.fetched, limit=10)
        # Just ensure it executes without error
        session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# ContentStorageService — get_pushable
# ---------------------------------------------------------------------------


class TestContentStorageServiceGetPushable:
    async def test_get_pushable_returns_scored_content(self):
        session = _make_session()
        items = [_make_content(id=1, quality_score=9.0, pipeline_status=PipelineStatus.scored)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = items
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        pushable = await svc.get_pushable(min_score=6.0)
        assert len(pushable) == 1

    async def test_get_pushable_default_min_score(self):
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        svc = ContentStorageService(session)
        await svc.get_pushable()
        session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# SourceService
# ---------------------------------------------------------------------------


class TestSourceService:
    async def test_create_source_inserts_and_returns(self):
        session = _make_session()
        svc = SourceService(session)

        config = SourceConfigSchema(
            name="ArXiv CS",
            url="https://export.arxiv.org/rss/cs.AI",
            type="arxiv",
        )
        await svc.create(config)

        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    async def test_list_active_returns_sources(self):
        session = _make_session()
        sources = [_make_source(id=i) for i in range(2)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = sources
        session.execute.return_value = result_mock

        svc = SourceService(session)
        active = await svc.list_active()
        assert len(active) == 2

    async def test_mark_fetched_updates_timestamp(self):
        session = _make_session()
        source = _make_source(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = source
        session.execute.return_value = result_mock

        svc = SourceService(session)
        await svc.mark_fetched(1)

        assert source.last_fetched_at is not None
        session.commit.assert_called_once()

    async def test_mark_fetched_raises_on_missing(self):
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        svc = SourceService(session)
        with pytest.raises(ValueError, match="Source.*not found"):
            await svc.mark_fetched(999)
