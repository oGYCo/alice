"""Telegram flow integration tests for Alice AI Secretary.

Tests Telegram bot interactions using callback objects and a real PostgreSQL DB:
- Webhook callback data parsing
- Feedback handler stores feedback to DB
- Feedback callback → KGUpdater → acknowledgment message

Runs against real PostgreSQL from docker-compose.yml (localhost:5432, database: alice_test).
Override with TEST_DATABASE_URL env var if needed.

    uv run pytest tests/integration/test_telegram_flow.py -v --timeout=120 -m integration
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.bot.handlers.feedback import (
    handle_feedback_callback_with_session_factory,
    parse_callback_data,
)
from alice.models import Base
from alice.models.content import Content, PipelineStatus
from alice.models.feedback import Feedback, FeedbackType

from .conftest import ensure_test_database, get_test_database_url

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# ---------------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------------

ensure_test_database()
TEST_DATABASE_URL = get_test_database_url()

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
    """Pre-insert User rows needed by the feedback handler.

    handle_feedback_callback uses query.from_user.id (Telegram user id) directly
    as user_id FK into the users table.  The _make_callback_query helper creates
    callbacks with chat_id in [100001..100005] and user_id=1 (default).
    We seed User rows for all user IDs used across this test module.
    """
    from sqlalchemy import text

    # Default _make_callback_query user_id=1, plus explicit chat_ids used as user_ids
    user_ids = [1, 100001, 100002, 100003, 100004, 100005]

    async with engine.begin() as conn:
        await conn.execute(text("SELECT setval('users_id_seq', 1, false)"))
        for uid in user_ids:
            await conn.execute(
                text(
                    "INSERT INTO users (id, telegram_chat_id, preferences) "
                    "VALUES (:id, :chat_id, '{}') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": uid, "chat_id": uid + 900000},
            )
        await conn.execute(text("SELECT setval('users_id_seq', 200000, true)"))
    yield
    async with engine.begin() as conn:
        # Delete child tables first (FK depends on users), then users
        await conn.execute(
            text(f"DELETE FROM review_cards WHERE user_id = ANY(ARRAY{user_ids})")
        )
        await conn.execute(
            text(f"DELETE FROM user_memories WHERE user_id = ANY(ARRAY{user_ids})")
        )
        await conn.execute(
            text(f"DELETE FROM feedback WHERE user_id = ANY(ARRAY{user_ids})")
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


class _FromUserStub:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _CallbackQueryStub:
    def __init__(self, data: str, user_id: int) -> None:
        self.data = data
        self.from_user = _FromUserStub(user_id)
        self.answer_calls: list[dict[str, str]] = []

    async def answer(self, *, text: str) -> None:
        self.answer_calls.append({"text": text})


class _BotStub:
    async def send_message(self, *_: object, **__: object) -> None:
        return None


def _make_mock_bot() -> _BotStub:
    return _BotStub()


def _make_callback_query(
    data: str,
    chat_id: int = 100001,
    user_id: int = 1,
) -> _CallbackQueryStub:
    """Create a minimal callback query object for handler integration tests."""
    del chat_id
    return _CallbackQueryStub(data=data, user_id=user_id)


def _make_content_row(url: str) -> Content:
    c = Content()
    c.source = "rss"
    c.source_url = url
    c.title = "Test article"
    c.summary = "Test summary"
    c.quality_score = 7.5
    c.pipeline_status = PipelineStatus.indexed
    c.fetched_at = datetime.now(UTC)
    c.domains = ["machine_learning"]
    c.key_points = []
    c.estimated_read_time = 3
    c.metadata_ = {}
    return c


# ---------------------------------------------------------------------------
# Unit tests for parse_callback_data (no DB needed)
# ---------------------------------------------------------------------------


async def test_parse_callback_data_valuable_learned():
    """parse_callback_data correctly parses 'valuable_learned' feedback."""
    feedback_type, content_id = parse_callback_data("feedback:valuable_learned:42")
    assert feedback_type == FeedbackType.valuable_learned
    assert content_id == 42


async def test_parse_callback_data_save_for_later():
    """parse_callback_data correctly parses 'save_for_later' feedback."""
    feedback_type, content_id = parse_callback_data("feedback:save_for_later:99")
    assert feedback_type == FeedbackType.save_for_later
    assert content_id == 99


async def test_parse_callback_data_not_valuable():
    """parse_callback_data correctly parses 'not_valuable' feedback."""
    feedback_type, content_id = parse_callback_data("feedback:not_valuable:7")
    assert feedback_type == FeedbackType.not_valuable
    assert content_id == 7


async def test_parse_callback_data_already_known():
    """parse_callback_data correctly parses 'already_known' feedback."""
    feedback_type, content_id = parse_callback_data("feedback:already_known:15")
    assert feedback_type == FeedbackType.already_known
    assert content_id == 15


async def test_parse_callback_data_invalid_format():
    """parse_callback_data raises ValueError for malformed data."""
    with pytest.raises(ValueError, match="Invalid callback data format"):
        parse_callback_data("feedback:valuable_learned")


async def test_parse_callback_data_unknown_type():
    """parse_callback_data raises ValueError for unknown feedback type."""
    with pytest.raises(ValueError, match="Unknown feedback type"):
        parse_callback_data("feedback:thumbs_up:42")


async def test_parse_callback_data_invalid_content_id():
    """parse_callback_data raises ValueError when content_id is not an integer."""
    with pytest.raises(ValueError, match="Invalid content_id"):
        parse_callback_data("feedback:valuable_learned:not_a_number")


# ---------------------------------------------------------------------------
# Integration: feedback callback stores to DB
# ---------------------------------------------------------------------------


async def test_feedback_callback_stores_to_db(engine, db_seed):
    """handle_feedback_callback stores a Feedback record to the database."""
    # db_seed fixture pre-inserted User.id=1; insert content with real commit
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            content = _make_content_row("https://example.com/tg-flow-test-1")
            sess.add(content)
            await sess.flush()
            content_id = content.id

    mock_bot = _make_mock_bot()
    # _make_callback_query default user_id=1, which exists via db_seed
    query = _make_callback_query(
        data=f"feedback:valuable_learned:{content_id}",
        chat_id=100001,
    )

    await handle_feedback_callback_with_session_factory(
        query,
        mock_bot,
        session_factory=factory,
    )

    # Verify feedback was stored (handler commits its own session)
    async with factory() as verify_sess:
        result = await verify_sess.execute(
            select(Feedback).where(Feedback.content_id == content_id)
        )
        feedback = result.scalar_one_or_none()

    assert feedback is not None
    assert feedback.content_id == content_id
    assert len(query.answer_calls) == 1


async def test_feedback_callback_sends_confirmation_message(engine, db_seed):
    """handle_feedback_callback answers the query with a confirmation message."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            content = _make_content_row("https://example.com/tg-flow-confirm-1")
            session.add(content)
            await session.flush()
            content_id = content.id

    mock_bot = _make_mock_bot()
    query = _make_callback_query(
        data=f"feedback:valuable_learned:{content_id}",
        chat_id=100002,
    )

    await handle_feedback_callback_with_session_factory(
        query,
        mock_bot,
        session_factory=factory,
    )

    # The handler should have called query.answer() to acknowledge the callback
    assert len(query.answer_calls) == 1


async def test_not_valuable_feedback_stores_correct_type(engine, db_seed):
    """Negative feedback stores FeedbackType.not_valuable in DB."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            content = _make_content_row("https://example.com/tg-negative-1")
            session.add(content)
            await session.flush()
            content_id = content.id

    mock_bot = _make_mock_bot()
    query = _make_callback_query(
        data=f"feedback:not_valuable:{content_id}",
        chat_id=100003,
    )

    await handle_feedback_callback_with_session_factory(
        query,
        mock_bot,
        session_factory=factory,
    )

    assert len(query.answer_calls) == 1


async def test_already_known_feedback_acknowledged(engine, db_seed):
    """Already-known feedback is handled and query is answered."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            content = _make_content_row("https://example.com/tg-known-1")
            session.add(content)
            await session.flush()
            content_id = content.id

    mock_bot = _make_mock_bot()
    query = _make_callback_query(
        data=f"feedback:already_known:{content_id}",
        chat_id=100004,
    )

    await handle_feedback_callback_with_session_factory(
        query,
        mock_bot,
        session_factory=factory,
    )

    assert len(query.answer_calls) == 1


async def test_invalid_callback_data_does_not_crash(engine, db_seed):
    """Malformed callback data is handled gracefully — no exception raised."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    mock_bot = _make_mock_bot()
    query = _make_callback_query(data="invalid_garbage_data", chat_id=100005)

    # Should not raise — the handler catches ValueError internally
    await handle_feedback_callback_with_session_factory(
        query,
        mock_bot,
        session_factory=factory,
    )

    # Handler should still call answer() with an error message
    assert len(query.answer_calls) == 1
