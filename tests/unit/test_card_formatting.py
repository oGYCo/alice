"""Tests for push card formatting in build_push_card().

Tests card type inference, card text formatting, and button layouts for all 3 card types.
"""

from datetime import UTC, datetime

import pytest
from aiogram.types import InlineKeyboardMarkup

from alice.bot.handlers.push import _escape_markdown, _get_card_type, build_push_card
from alice.schemas.content import ContentResponseSchema

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_schema(content_type: str = "deep_knowledge", **overrides) -> ContentResponseSchema:
    """Build ContentResponseSchema with defaults, allowing field overrides.

    This helper ensures we create real Pydantic models, not mocks, to avoid
    validation errors seen in test_push_service.py.
    """
    defaults = dict(
        id=1,
        source="rss",
        source_url="https://example.com/article",
        title="Test Title",
        pipeline_status="indexed",
        quality_score=8.0,
        summary="Test summary of the article.",
        key_points=["Point 1", "Point 2"],
        domains=["AI"],
        estimated_read_time=10,
        metadata_={
            "content_type": content_type,
            "push_reason": "Relevant to work",
            "reading_advice": "Read carefully",
        },
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return ContentResponseSchema(**defaults)


@pytest.fixture
def deep_knowledge_schema() -> ContentResponseSchema:
    """Default deep_knowledge card schema."""
    return _make_schema()


@pytest.fixture
def time_sensitive_schema() -> ContentResponseSchema:
    """Time-sensitive card schema."""
    return _make_schema(
        content_type="time_sensitive",
        metadata_={
            "content_type": "time_sensitive",
            "what": "vLLM released v0.5.0",
            "impact": "30% faster inference",
            "push_reason": "Framework update",
            "reading_advice": "Quick check",
        },
    )


@pytest.fixture
def thought_provoking_schema() -> ContentResponseSchema:
    """Thought-provoking card schema."""
    return _make_schema(
        content_type="thought_provoking",
        metadata_={
            "content_type": "thought_provoking",
            "push_reason": "New perspective",
            "reading_advice": "Reflects on your work",
        },
    )


# ---------------------------------------------------------------------------
# TestGetCardType
# ---------------------------------------------------------------------------


class TestGetCardType:
    """Card type inference from metadata.content_type."""

    def test_deep_knowledge_default(self, deep_knowledge_schema: ContentResponseSchema) -> None:
        """No metadata_ or default content_type → returns 'deep_knowledge'."""
        schema = _make_schema(metadata_={})
        result = _get_card_type(schema)
        assert result == "deep_knowledge"

    def test_time_sensitive(self, time_sensitive_schema: ContentResponseSchema) -> None:
        """content_type='time_sensitive' → returns 'time_sensitive'."""
        result = _get_card_type(time_sensitive_schema)
        assert result == "time_sensitive"

    def test_thought_provoking(self, thought_provoking_schema: ContentResponseSchema) -> None:
        """content_type='thought_provoking' → returns 'thought_provoking'."""
        result = _get_card_type(thought_provoking_schema)
        assert result == "thought_provoking"

    def test_thought_maps_to_thought_provoking(self) -> None:
        """content_type='thought' (from understanding LLM) → returns 'thought_provoking'."""
        schema = _make_schema(
            content_type="thought",
            metadata_={"content_type": "thought"},
        )
        result = _get_card_type(schema)
        assert result == "thought_provoking"

    def test_news_maps_to_time_sensitive(self) -> None:
        """content_type='news' (from understanding LLM) → returns 'time_sensitive'."""
        schema = _make_schema(
            content_type="news",
            metadata_={"content_type": "news"},
        )
        result = _get_card_type(schema)
        assert result == "time_sensitive"


# ---------------------------------------------------------------------------
# TestBuildPushCard
# ---------------------------------------------------------------------------


class TestBuildPushCard:
    """Card text formatting and return type."""

    def test_deep_knowledge_contains_title(
        self, deep_knowledge_schema: ContentResponseSchema
    ) -> None:
        """Deep knowledge card text contains the title."""
        text, _ = build_push_card(deep_knowledge_schema)
        assert deep_knowledge_schema.title in text

    def test_deep_knowledge_contains_core_content_header(
        self, deep_knowledge_schema: ContentResponseSchema
    ) -> None:
        """Deep knowledge card text contains '核心内容' (core content header)."""
        text, _ = build_push_card(deep_knowledge_schema)
        assert "核心内容" in text

    def test_deep_knowledge_contains_push_reason(
        self, deep_knowledge_schema: ContentResponseSchema
    ) -> None:
        """Deep knowledge card text contains '推送原因' (push reason header)."""
        text, _ = build_push_card(deep_knowledge_schema)
        assert "推送原因" in text

    def test_time_sensitive_contains_what(
        self, time_sensitive_schema: ContentResponseSchema
    ) -> None:
        """Time-sensitive card text contains 'What' section with the what field."""
        text, _ = build_push_card(time_sensitive_schema)
        assert "What" in text or "What:" in text or "WHAT" in text or "what" in text
        # Also verify 'what' content is present
        assert "vLLM" in text or "released" in text

    def test_thought_provoking_contains_summary(
        self, thought_provoking_schema: ContentResponseSchema
    ) -> None:
        """Thought-provoking card text contains the summary."""
        text, _ = build_push_card(thought_provoking_schema)
        assert thought_provoking_schema.summary in text

    def test_returns_tuple_text_and_markup(
        self, deep_knowledge_schema: ContentResponseSchema
    ) -> None:
        """build_push_card() returns a tuple of (str, InlineKeyboardMarkup)."""
        result = build_push_card(deep_knowledge_schema)
        assert isinstance(result, tuple)
        assert len(result) == 2
        text, markup = result
        assert isinstance(text, str)
        assert isinstance(markup, InlineKeyboardMarkup)


# ---------------------------------------------------------------------------
# TestButtonLayouts
# ---------------------------------------------------------------------------


class TestButtonLayouts:
    """Button counts and layouts for each card type."""

    def test_deep_knowledge_has_6_buttons(
        self, deep_knowledge_schema: ContentResponseSchema
    ) -> None:
        """Deep knowledge card has 6 total buttons (2 rows × 3)."""
        _, markup = build_push_card(deep_knowledge_schema)
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 6
        # Also verify 2 rows
        assert len(markup.inline_keyboard) == 2

    def test_time_sensitive_has_2_buttons(
        self, time_sensitive_schema: ContentResponseSchema
    ) -> None:
        """Time-sensitive card has 2 total buttons (1 row × 2)."""
        _, markup = build_push_card(time_sensitive_schema)
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 2
        # Also verify 1 row
        assert len(markup.inline_keyboard) == 1

    def test_thought_provoking_has_4_buttons(
        self, thought_provoking_schema: ContentResponseSchema
    ) -> None:
        """Thought-provoking card has 4 total buttons (1 row × 4)."""
        _, markup = build_push_card(thought_provoking_schema)
        total_buttons = sum(len(row) for row in markup.inline_keyboard)
        assert total_buttons == 4
        # Also verify 1 row
        assert len(markup.inline_keyboard) == 1

    def test_time_sensitive_buttons_have_correct_callbacks(
        self, time_sensitive_schema: ContentResponseSchema
    ) -> None:
        """Time-sensitive buttons have correct callback data prefixes."""
        _, markup = build_push_card(time_sensitive_schema)
        buttons = markup.inline_keyboard[0]

        # First button: valuable_learned
        assert buttons[0].callback_data.startswith("feedback:valuable_learned:")

        # Second button: save_for_later
        assert buttons[1].callback_data.startswith("feedback:save_for_later:")


# ---------------------------------------------------------------------------
# TestEscapeMarkdown
# ---------------------------------------------------------------------------


class TestEscapeMarkdown:
    """Telegram Markdown v1 special character escaping."""

    def test_escapes_underscores(self) -> None:
        assert _escape_markdown("hello_world") == r"hello\_world"

    def test_escapes_asterisks(self) -> None:
        assert _escape_markdown("bold*text*here") == r"bold\*text\*here"

    def test_escapes_backticks(self) -> None:
        assert _escape_markdown("use `code` here") == r"use \`code\` here"

    def test_escapes_square_brackets(self) -> None:
        assert _escape_markdown("[link](url)") == r"\[link\](url)"

    def test_empty_string(self) -> None:
        assert _escape_markdown("") == ""

    def test_plain_text_unchanged(self) -> None:
        assert _escape_markdown("no special chars") == "no special chars"

    def test_multiple_special_chars(self) -> None:
        result = _escape_markdown("a_b*c`d[e]f")
        assert result == r"a\_b\*c\`d\[e\]f"

    def test_build_push_card_escapes_title_with_underscores(self) -> None:
        """Title with underscores is escaped in the rendered card."""
        schema = _make_schema(title="flash_attention_v3")
        text, _ = build_push_card(schema)
        assert "flash\\_attention\\_v3" in text
