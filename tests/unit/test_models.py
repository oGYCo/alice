"""Unit tests for SQLAlchemy models."""

import pytest

from alice.models.content import Content, PipelineStatus
from alice.models.feedback import Feedback, FeedbackType
from alice.models.source import Source, SourceType
from alice.models.user import User


def test_content_pipeline_status_values():
    """Test that PipelineStatus enum has correct values."""
    assert PipelineStatus.fetched == "fetched"
    assert PipelineStatus.gatekept == "gatekept"
    assert PipelineStatus.understood == "understood"
    assert PipelineStatus.scored == "scored"
    assert PipelineStatus.indexed == "indexed"
    assert PipelineStatus.failed == "failed"


def test_source_type_values():
    """Test that SourceType enum has correct values."""
    assert SourceType.rss == "rss"
    assert SourceType.arxiv == "arxiv"


def test_feedback_type_values():
    """Test that FeedbackType enum has correct values."""
    assert FeedbackType.valuable_learned == "valuable_learned"
    assert FeedbackType.save_for_later == "save_for_later"
    assert FeedbackType.not_valuable == "not_valuable"
    assert FeedbackType.already_known == "already_known"


def test_content_model_has_required_fields():
    """Test that Content model has all required fields."""
    # Check all required columns exist
    columns = {col.name for col in Content.__table__.columns}
    required = {
        "id",
        "source",
        "source_url",
        "pipeline_status",
        "quality_score",
        "summary",
        "key_points",
        "domains",
        "created_at",
        "updated_at",
    }
    assert required.issubset(columns), f"Missing columns: {required - columns}"


def test_pipeline_status_invalid_value():
    """Test that invalid pipeline status raises ValueError."""
    with pytest.raises(ValueError):
        PipelineStatus("invalid_value")


def test_user_model_has_telegram_field():
    """Test that User model has telegram_chat_id field."""
    columns = {col.name for col in User.__table__.columns}
    assert "telegram_chat_id" in columns


def test_source_type_enum():
    """Test SourceType enum values."""
    assert len(SourceType) == 2
    enum_values = {e.value for e in SourceType}
    assert enum_values == {"rss", "arxiv"}


def test_feedback_type_enum():
    """Test FeedbackType enum values."""
    assert len(FeedbackType) == 4
    enum_values = {e.value for e in FeedbackType}
    assert enum_values == {
        "valuable_learned",
        "save_for_later",
        "not_valuable",
        "already_known",
    }


def test_user_model_structure():
    """Test User model table structure."""
    columns = {col.name for col in User.__table__.columns}
    assert "id" in columns
    assert "telegram_chat_id" in columns
    assert "preferences" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_source_model_structure():
    """Test Source model table structure."""
    columns = {col.name for col in Source.__table__.columns}
    assert "id" in columns
    assert "type" in columns
    assert "name" in columns
    assert "url" in columns
    assert "config" in columns
    assert "is_active" in columns
    assert "last_fetched_at" in columns
    assert "fetch_interval_minutes" in columns


def test_content_model_structure():
    """Test Content model table structure."""
    columns = {col.name for col in Content.__table__.columns}
    assert "id" in columns
    assert "user_id" in columns
    assert "source" in columns
    assert "source_url" in columns
    assert "title" in columns
    assert "author" in columns
    assert "published_at" in columns
    assert "extracted_text" in columns
    assert "pipeline_status" in columns
    assert "quality_score" in columns
    assert "summary" in columns
    assert "key_points" in columns
    assert "domains" in columns
    assert "estimated_read_time" in columns


def test_feedback_model_structure():
    """Test Feedback model table structure."""
    columns = {col.name for col in Feedback.__table__.columns}
    assert "id" in columns
    assert "content_id" in columns
    assert "user_id" in columns
    assert "type" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
