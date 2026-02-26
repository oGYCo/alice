"""Integration tests for bot feedback webhook integration.

Requires a real PostgreSQL test database.
Set TEST_DATABASE_URL env var to run:
    export TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/alice_test"
    uv run pytest tests/integration/test_bot_integration.py -v -m integration

Skip automatically when TEST_DATABASE_URL is not set.
"""

import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.bot.handlers.feedback import handle_feedback_callback, parse_callback_data
from alice.models.base import Base
from alice.models.feedback import Feedback, FeedbackType

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# ---------------------------------------------------------------------------
# Skip logic
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

# Skip entire module if TEST_DATABASE_URL not set
if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL not set — skipping integration tests", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create async engine connected to test DB."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def db_seed(engine):
    """Pre-insert Content and User rows with specific IDs for FK constraints in tests.

    The feedback handler uses query.from_user.id directly as user_id (FK → users.id).
    We must pre-insert User rows with those exact IDs, and Content rows with the
    hardcoded content_ids used in each test.
    """
    from datetime import UTC, datetime

    from sqlalchemy import text

    content_ids = [123, 200, 456, 500, 600, 601, 700]
    # These are the Telegram user IDs used in tests, stored as users.id via handler
    user_ids = [999, 888, 111, 222, 1001, 1002, 2000, 3000]

    async with engine.begin() as conn:
        # Seed users with forced IDs
        await conn.execute(text("SELECT setval('users_id_seq', 100, false)"))
        for uid in user_ids:
            await conn.execute(
                text(
                    "INSERT INTO users (id, telegram_chat_id, preferences) "
                    "VALUES (:id, :chat_id, '{}') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": uid, "chat_id": uid * 10},  # unique chat_id != id
            )
        await conn.execute(text("SELECT setval('users_id_seq', 10000, true)"))

        # Seed content rows with forced IDs
        await conn.execute(text("SELECT setval('content_id_seq', 100, false)"))
        for cid in content_ids:
            await conn.execute(
                text(
                    "INSERT INTO content (id, source, source_url, title, metadata, "
                    "pipeline_status, fetched_at, domains, key_points, estimated_read_time) "
                    "VALUES (:id, 'rss', :url, :title, '{}', 'indexed', :now, '[]', '[]', 1) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": cid,
                    "url": f"https://example.com/seed/{cid}",
                    "title": f"Seed article {cid}",
                    "now": datetime.now(UTC),
                },
            )
        # Advance the sequences past our seeded IDs
        await conn.execute(text("SELECT setval('content_id_seq', 1000, true)"))
    yield
    # Cleanup (feedback FK-depends on content/users, clean feedback first)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"DELETE FROM feedback WHERE content_id = ANY(ARRAY{content_ids})")
        )
        await conn.execute(
            text(f"DELETE FROM content WHERE id = ANY(ARRAY{content_ids})")
        )
        await conn.execute(
            text(f"DELETE FROM users WHERE id = ANY(ARRAY{user_ids})")
        )


@pytest_asyncio.fixture(loop_scope="module")
async def session(engine, db_seed):
    """Provide a session with savepoint isolation.

    Services may call session.commit(); join_transaction_mode='create_savepoint'
    converts those commits into SAVEPOINT releases instead of real commits.
    The outer transaction is rolled back after each test.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with factory() as sess:
            yield sess
        await trans.rollback()


# ---------------------------------------------------------------------------
# parse_callback_data unit tests
# ---------------------------------------------------------------------------


async def test_parse_callback_data_valid_valuable_learned():
    """parse_callback_data handles 'feedback:valuable_learned:42'."""
    feedback_type, content_id = parse_callback_data("feedback:valuable_learned:42")
    assert feedback_type == FeedbackType.valuable_learned
    assert content_id == 42


async def test_parse_callback_data_valid_save_for_later():
    """parse_callback_data handles 'feedback:save_for_later:99'."""
    feedback_type, content_id = parse_callback_data("feedback:save_for_later:99")
    assert feedback_type == FeedbackType.save_for_later
    assert content_id == 99


async def test_parse_callback_data_valid_not_valuable():
    """parse_callback_data handles 'feedback:not_valuable:1'."""
    feedback_type, content_id = parse_callback_data("feedback:not_valuable:1")
    assert feedback_type == FeedbackType.not_valuable
    assert content_id == 1


async def test_parse_callback_data_valid_already_known():
    """parse_callback_data handles 'feedback:already_known:777'."""
    feedback_type, content_id = parse_callback_data("feedback:already_known:777")
    assert feedback_type == FeedbackType.already_known
    assert content_id == 777


async def test_parse_callback_data_invalid_format_missing_parts():
    """parse_callback_data raises ValueError for 'feedback:valuable_learned' (missing content_id)."""
    with pytest.raises(ValueError, match="Invalid callback data format"):
        parse_callback_data("feedback:valuable_learned")


async def test_parse_callback_data_invalid_format_wrong_prefix():
    """parse_callback_data raises ValueError for 'action:valuable_learned:42'."""
    with pytest.raises(ValueError, match="Invalid callback data format"):
        parse_callback_data("action:valuable_learned:42")


async def test_parse_callback_data_unknown_feedback_type():
    """parse_callback_data raises ValueError for unknown feedback type."""
    with pytest.raises(ValueError, match="Unknown feedback type"):
        parse_callback_data("feedback:unknown_type:42")


async def test_parse_callback_data_invalid_content_id():
    """parse_callback_data raises ValueError for non-integer content_id."""
    with pytest.raises(ValueError, match="Invalid content_id in callback data"):
        parse_callback_data("feedback:valuable_learned:not_a_number")


# ---------------------------------------------------------------------------
# Bot handler integration tests (with real DB)
# ---------------------------------------------------------------------------


async def test_handle_feedback_callback_stores_to_db(session, monkeypatch):
    """handle_feedback_callback stores Feedback record to test DB."""
    # Mock AsyncSessionLocal to use test session
    monkeypatch.setattr(
        "alice.bot.handlers.feedback.AsyncSessionLocal",
        lambda: AsyncMock(
            __aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=None)
        ),
    )

    # Create mock CallbackQuery with data 'feedback:valuable_learned:123'
    query = AsyncMock()
    query.data = "feedback:valuable_learned:123"
    query.from_user.id = 999

    # Create mock Bot object
    bot = AsyncMock()

    # Call handler
    await handle_feedback_callback(query, bot)

    # Verify Feedback was stored
    stmt = select(Feedback).where(Feedback.content_id == 123, Feedback.user_id == 999)
    result = await session.execute(stmt)
    feedback = result.scalar_one_or_none()

    assert feedback is not None
    assert feedback.content_id == 123
    assert feedback.user_id == 999
    assert feedback.type == FeedbackType.valuable_learned


async def test_handle_feedback_callback_all_feedback_types(session, monkeypatch):
    """handle_feedback_callback handles all four feedback types."""
    test_cases = [
        ("valuable_learned", FeedbackType.valuable_learned),
        ("save_for_later", FeedbackType.save_for_later),
        ("not_valuable", FeedbackType.not_valuable),
        ("already_known", FeedbackType.already_known),
    ]

    for type_str, expected_type in test_cases:
        # Mock AsyncSessionLocal
        monkeypatch.setattr(
            "alice.bot.handlers.feedback.AsyncSessionLocal",
            lambda: AsyncMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=None),
            ),
        )

        query = AsyncMock()
        query.data = f"feedback:{type_str}:200"
        query.from_user.id = 888

        bot = AsyncMock()

        await handle_feedback_callback(query, bot)

        stmt = select(Feedback).where(
            Feedback.content_id == 200,
            Feedback.user_id == 888,
            Feedback.type == expected_type,
        )
        result = await session.execute(stmt)
        feedback = result.scalar_one_or_none()

        assert feedback is not None, f"Feedback not stored for type {type_str}"
        assert feedback.type == expected_type


async def test_handle_feedback_callback_answers_query(session, monkeypatch):
    """handle_feedback_callback calls query.answer() after storing."""
    monkeypatch.setattr(
        "alice.bot.handlers.feedback.AsyncSessionLocal",
        lambda: AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=None),
        ),
    )

    query = AsyncMock()
    query.data = "feedback:valuable_learned:456"
    query.from_user.id = 111

    bot = AsyncMock()

    await handle_feedback_callback(query, bot)

    # Verify query.answer was called with a text message
    query.answer.assert_called_once()
    call_kwargs = query.answer.call_args.kwargs
    assert "text" in call_kwargs
    assert call_kwargs["text"] == "✅ 已记录！知识图谱已更新。"


async def test_handle_feedback_callback_invalid_data(session, monkeypatch):
    """handle_feedback_callback handles invalid callback data gracefully."""
    monkeypatch.setattr(
        "alice.bot.handlers.feedback.AsyncSessionLocal",
        lambda: AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=None),
        ),
    )

    query = AsyncMock()
    query.data = "invalid:callback:data"
    query.from_user.id = 222

    bot = AsyncMock()

    await handle_feedback_callback(query, bot)

    # Verify query.answer was called with error message (doesn't raise)
    query.answer.assert_called_once()
    call_kwargs = query.answer.call_args.kwargs
    assert call_kwargs["text"] == "无效的反馈数据。"

    # Verify no Feedback was stored
    stmt = select(Feedback).where(Feedback.user_id == 222)
    result = await session.execute(stmt)
    feedback_list = result.scalars().all()
    assert len(feedback_list) == 0


async def test_handle_feedback_callback_multiple_users(session, monkeypatch):
    """handle_feedback_callback isolates feedback by user_id."""
    monkeypatch.setattr(
        "alice.bot.handlers.feedback.AsyncSessionLocal",
        lambda: AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=None),
        ),
    )

    # First user provides feedback
    query1 = AsyncMock()
    query1.data = "feedback:valuable_learned:500"
    query1.from_user.id = 1001

    bot = AsyncMock()
    await handle_feedback_callback(query1, bot)

    # Second user provides feedback on same content
    query2 = AsyncMock()
    query2.data = "feedback:not_valuable:500"
    query2.from_user.id = 1002

    await handle_feedback_callback(query2, bot)

    # Verify both records exist with different types and user_ids
    stmt = select(Feedback).where(Feedback.content_id == 500).order_by(Feedback.user_id)
    result = await session.execute(stmt)
    feedbacks = result.scalars().all()

    assert len(feedbacks) == 2
    assert feedbacks[0].user_id == 1001
    assert feedbacks[0].type == FeedbackType.valuable_learned
    assert feedbacks[1].user_id == 1002
    assert feedbacks[1].type == FeedbackType.not_valuable


async def test_handle_feedback_callback_same_user_multiple_feedbacks(session, monkeypatch):
    """handle_feedback_callback allows same user to feedback on multiple contents."""
    monkeypatch.setattr(
        "alice.bot.handlers.feedback.AsyncSessionLocal",
        lambda: AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=None),
        ),
    )

    user_id = 2000

    # First feedback
    query1 = AsyncMock()
    query1.data = "feedback:valuable_learned:600"
    query1.from_user.id = user_id

    bot = AsyncMock()
    await handle_feedback_callback(query1, bot)

    # Second feedback
    query2 = AsyncMock()
    query2.data = "feedback:save_for_later:601"
    query2.from_user.id = user_id

    await handle_feedback_callback(query2, bot)

    # Verify both records exist
    stmt = select(Feedback).where(Feedback.user_id == user_id).order_by(Feedback.content_id)
    result = await session.execute(stmt)
    feedbacks = result.scalars().all()

    assert len(feedbacks) == 2
    assert feedbacks[0].content_id == 600
    assert feedbacks[0].type == FeedbackType.valuable_learned
    assert feedbacks[1].content_id == 601
    assert feedbacks[1].type == FeedbackType.save_for_later


async def test_feedback_timestamps_set_automatically(session, monkeypatch):
    """Feedback record has created_at and updated_at set automatically."""
    monkeypatch.setattr(
        "alice.bot.handlers.feedback.AsyncSessionLocal",
        lambda: AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=None),
        ),
    )

    query = AsyncMock()
    query.data = "feedback:valuable_learned:700"
    query.from_user.id = 3000

    bot = AsyncMock()
    await handle_feedback_callback(query, bot)

    stmt = select(Feedback).where(Feedback.content_id == 700)
    result = await session.execute(stmt)
    feedback = result.scalar_one()

    assert feedback.created_at is not None
    assert feedback.updated_at is not None
    assert feedback.created_at == feedback.updated_at
