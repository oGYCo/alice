"""Unit tests for PushService.

TDD: tests written FIRST (RED), then implementation (GREEN).
asyncio_mode = 'auto' — no @pytest.mark.asyncio needed.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from alice.models.content import Content, PipelineStatus
from alice.schemas.content import ContentResponseSchema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> MagicMock:
    """Build a MagicMock that looks like a Content ORM object."""
    defaults = dict(
        id=1,
        title="FlashAttention-3: Fast and Accurate",
        source="rss",
        source_url="https://example.com/flashattention3",
        summary="FlashAttention-3 uses hardware async to accelerate attention.",
        key_points=["WGMMA instruction overlap", "TMA async transfer", "75% peak FLOPS"],
        domains=["AI", "systems"],
        estimated_read_time=12,
        quality_score=8.5,
        pipeline_status=PipelineStatus.indexed,
        pushed_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Content)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_session():
    """Return a mock AsyncSession (add is sync, commit is async)."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_scalars_result(items: list) -> MagicMock:
    """Wrap items in scalars().all() mock chain."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


# ---------------------------------------------------------------------------
# get_next_push_batch
# ---------------------------------------------------------------------------


class TestGetNextPushBatch:
    async def test_returns_indexed_unpushed_content_ordered_by_score(self):
        """Should query content with pipeline_status=indexed, pushed_at=None,
        ordered by quality_score DESC, limited to `limit`."""
        from alice.services.push import PushService

        session = _make_session()
        items = [_make_content(id=1, quality_score=9.0), _make_content(id=2, quality_score=7.5)]
        session.execute = AsyncMock(return_value=_make_scalars_result(items))

        svc = PushService()
        result = await svc.get_next_push_batch(session, user_id=42, limit=5)

        assert result == items
        session.execute.assert_called_once()

    async def test_respects_limit_parameter(self):
        """limit param should be forwarded to the query."""
        from alice.services.push import PushService

        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalars_result([]))

        svc = PushService()
        await svc.get_next_push_batch(session, user_id=1, limit=3)

        session.execute.assert_called_once()

    async def test_returns_empty_list_when_no_content(self):
        """Should return [] when no indexed+unpushed content exists."""
        from alice.services.push import PushService

        session = _make_session()
        session.execute = AsyncMock(return_value=_make_scalars_result([]))

        svc = PushService()
        result = await svc.get_next_push_batch(session, user_id=1, limit=5)

        assert result == []


# ---------------------------------------------------------------------------
# format_push_card
# ---------------------------------------------------------------------------


class TestFormatPushCard:
    def test_returns_string(self):
        """format_push_card should return a non-empty string."""
        from alice.services.push import PushService

        content = _make_content()
        svc = PushService()
        text = svc.format_push_card(content)

        assert isinstance(text, str)
        assert len(text) > 0

    def test_includes_title(self):
        """Card text should include the content title."""
        from alice.services.push import PushService

        content = _make_content(title="My Amazing Article")
        svc = PushService()
        text = svc.format_push_card(content)

        assert "My Amazing Article" in text

    def test_includes_summary(self):
        """Card text should include the summary."""
        from alice.services.push import PushService

        content = _make_content(summary="A deep dive into async hardware.")
        svc = PushService()
        text = svc.format_push_card(content)

        assert "A deep dive into async hardware." in text

    def test_includes_key_points(self):
        """Card text should include all key points as bullet items."""
        from alice.services.push import PushService

        content = _make_content(key_points=["Point Alpha", "Point Beta"])
        svc = PushService()
        text = svc.format_push_card(content)

        assert "Point Alpha" in text
        assert "Point Beta" in text

    def test_includes_source_url(self):
        """Card text should include the source URL."""
        from alice.services.push import PushService

        content = _make_content(source_url="https://example.com/article")
        svc = PushService()
        text = svc.format_push_card(content)

        assert "https://example.com/article" in text

    def test_handles_missing_title(self):
        """Should render gracefully when title is None."""
        from alice.services.push import PushService

        content = _make_content(title=None)
        svc = PushService()
        text = svc.format_push_card(content)

        assert isinstance(text, str)
        assert len(text) > 0

    def test_handles_empty_key_points(self):
        """Should render without crashing when key_points is None."""
        from alice.services.push import PushService

        content = _make_content(key_points=None)
        svc = PushService()
        text = svc.format_push_card(content)

        assert isinstance(text, str)

    def test_includes_read_time_when_available(self):
        """Card text should include estimated_read_time."""
        from alice.services.push import PushService

        content = _make_content(estimated_read_time=8)
        svc = PushService()
        text = svc.format_push_card(content)

        assert "8" in text


# ---------------------------------------------------------------------------
# deliver_push
# ---------------------------------------------------------------------------


class TestDeliverPush:
    async def test_calls_send_push_for_each_content(self):
        """deliver_push should call send_push once per content item."""
        from alice.services.push import PushService

        session = _make_session()
        bot = MagicMock()
        content1 = _make_content(id=1)
        content2 = _make_content(id=2)

        with patch("alice.services.push.send_push", new_callable=AsyncMock) as mock_send:
            svc = PushService()
            await svc.deliver_push(
                bot=bot,
                user_id=42,
                chat_id=100,
                content_list=[content1, content2],
                session=session,
            )

        assert mock_send.call_count == 2

    async def test_records_pushed_at_timestamp(self):
        """deliver_push should set pushed_at on each delivered content."""
        from alice.services.push import PushService

        session = _make_session()
        bot = MagicMock()
        content = _make_content(id=1, pushed_at=None)

        with patch("alice.services.push.send_push", new_callable=AsyncMock):
            svc = PushService()
            await svc.deliver_push(
                bot=bot,
                user_id=42,
                chat_id=100,
                content_list=[content],
                session=session,
            )

        # pushed_at should be set to a datetime
        assert content.pushed_at is not None
        assert isinstance(content.pushed_at, datetime)

    async def test_commits_after_delivery(self):
        """deliver_push should commit the session after updating pushed_at."""
        from alice.services.push import PushService

        session = _make_session()
        bot = MagicMock()
        content = _make_content(id=1)

        with patch("alice.services.push.send_push", new_callable=AsyncMock):
            svc = PushService()
            await svc.deliver_push(
                bot=bot,
                user_id=42,
                chat_id=100,
                content_list=[content],
                session=session,
            )

        session.commit.assert_called_once()

    async def test_passes_content_schema_to_send_push(self):
        """deliver_push should pass a ContentResponseSchema to send_push."""
        from alice.services.push import PushService

        session = _make_session()
        bot = MagicMock()
        content = _make_content(id=1)
        content.domains = ["AI"]

        captured_calls = []

        async def fake_send_push(*, bot, chat_id, content):
            captured_calls.append(content)

        with patch("alice.services.push.send_push", side_effect=fake_send_push):
            svc = PushService()
            await svc.deliver_push(
                bot=bot,
                user_id=42,
                chat_id=100,
                content_list=[content],
                session=session,
            )

        assert len(captured_calls) == 1
        assert isinstance(captured_calls[0], ContentResponseSchema)

    async def test_empty_list_does_nothing(self):
        """deliver_push with empty list should not call send_push."""
        from alice.services.push import PushService

        session = _make_session()
        bot = MagicMock()

        with patch("alice.services.push.send_push", new_callable=AsyncMock) as mock_send:
            svc = PushService()
            await svc.deliver_push(
                bot=bot,
                user_id=42,
                chat_id=100,
                content_list=[],
                session=session,
            )

        mock_send.assert_not_called()
        session.commit.assert_not_called()
