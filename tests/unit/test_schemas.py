"""Tests for Pydantic schemas validation."""

import pytest
from pydantic import ValidationError

from alice.schemas.content import (
    ContentDetailSchema,
    ContentResponseSchema,
    ContentUnderstandingSchema,
    RawContentSchema,
)
from alice.schemas.feedback import FeedbackCreateSchema, FeedbackType
from alice.schemas.gatekeeper import GatekeeperDecision
from alice.schemas.pipeline import PipelineStatus, PipelineTaskSchema
from alice.schemas.quality import QualityScoreSchema
from alice.schemas.source import SourceConfigSchema


class TestRawContentSchema:
    """Tests for RawContentSchema."""

    def test_raw_content_schema_valid(self):
        """Test that RawContentSchema accepts valid data."""
        content = RawContentSchema(
            source="rss",
            source_url="https://example.com/article",
            title="Test Article",
            raw_text="Some content here",
        )
        assert content.source == "rss"
        assert content.extraction_failed is False
        assert content.metadata == {}

    def test_raw_content_schema_invalid_missing_url(self):
        """Test that missing source_url raises ValidationError."""
        with pytest.raises(ValidationError):
            RawContentSchema(source="rss")  # missing source_url


class TestQualityScoreSchema:
    """Tests for QualityScoreSchema."""

    def test_quality_score_valid_range(self):
        """Test quality score validation - must be 1-10."""
        score = QualityScoreSchema(score=8.5, reasoning="Good content")
        assert score.score == 8.5
        assert score.passes_threshold is True  # 8.5 >= 6.0

    def test_quality_score_above_range(self):
        """Test that score above 10 raises ValidationError."""
        with pytest.raises(ValidationError):
            QualityScoreSchema(score=15.0, reasoning="Too high")

    def test_quality_score_below_range(self):
        """Test that score below 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            QualityScoreSchema(score=0.0, reasoning="Too low")

    def test_quality_score_threshold(self):
        """Test that passes_threshold computed correctly."""
        low = QualityScoreSchema(score=3.0, reasoning="Low")
        assert low.passes_threshold is False

        high = QualityScoreSchema(score=7.0, reasoning="High")
        assert high.passes_threshold is True


class TestFeedbackCreateSchema:
    """Tests for FeedbackCreateSchema."""

    def test_feedback_type_valid(self):
        """Test valid feedback types."""
        fb = FeedbackCreateSchema(content_id=1, user_id=1, type=FeedbackType.valuable_learned)
        assert fb.type == "valuable_learned"

    def test_feedback_type_invalid(self):
        """Test that invalid feedback type raises ValueError."""
        with pytest.raises(ValueError):
            FeedbackType("invalid_type")


class TestGatekeeperDecision:
    """Tests for GatekeeperDecision."""

    def test_gatekeeper_decision_confidence_range(self):
        """Test gatekeeper confidence must be 0-1."""
        # Valid
        d = GatekeeperDecision(passed=True, reason="good", confidence=0.9)
        assert d.passed is True

        # Invalid - above range
        with pytest.raises(ValidationError):
            GatekeeperDecision(passed=True, reason="good", confidence=1.5)


class TestContentUnderstandingSchema:
    """Tests for ContentUnderstandingSchema."""

    def test_content_understanding_valid(self):
        """Test ContentUnderstandingSchema validation."""
        understanding = ContentUnderstandingSchema(
            summary="This article explains X",
            key_points=["Point 1", "Point 2"],
            domains=["AI", "ML"],
            estimated_read_time=5,
        )
        assert len(understanding.key_points) == 2
        assert understanding.estimated_read_time == 5

    def test_content_understanding_invalid_read_time(self):
        """Test that read_time < 1 is rejected."""
        with pytest.raises(ValidationError):
            ContentUnderstandingSchema(
                summary="Test",
                key_points=["p1"],
                domains=["AI"],
                estimated_read_time=0,
            )


class TestPipelineStatus:
    """Tests for PipelineStatus enum."""

    def test_pipeline_status_values(self):
        """Test all pipeline status values exist."""
        assert PipelineStatus.fetched == "fetched"
        assert PipelineStatus.indexed == "indexed"
        assert PipelineStatus.failed == "failed"


class TestSourceConfigSchema:
    """Tests for SourceConfigSchema."""

    def test_source_config_valid(self):
        """Test SourceConfigSchema with valid data."""
        src = SourceConfigSchema(name="HN Feed", url="https://hnrss.org/frontpage", type="rss")
        assert src.enabled is True
        assert src.fetch_interval_minutes == 30

    def test_source_config_invalid_type(self):
        """Test that invalid source type is rejected."""
        with pytest.raises(ValidationError):
            SourceConfigSchema(name="Bad", url="https://example.com", type="twitter")

    def test_source_config_fetch_interval_bounds(self):
        """Test fetch interval constraints."""
        # Valid: 5 minutes
        src = SourceConfigSchema(
            name="Test", url="https://example.com", type="rss", fetch_interval_minutes=5
        )
        assert src.fetch_interval_minutes == 5

        # Valid: 1440 minutes
        src = SourceConfigSchema(
            name="Test",
            url="https://example.com",
            type="rss",
            fetch_interval_minutes=1440,
        )
        assert src.fetch_interval_minutes == 1440

        # Invalid: < 5
        with pytest.raises(ValidationError):
            SourceConfigSchema(
                name="Test",
                url="https://example.com",
                type="rss",
                fetch_interval_minutes=4,
            )

        # Invalid: > 1440
        with pytest.raises(ValidationError):
            SourceConfigSchema(
                name="Test",
                url="https://example.com",
                type="rss",
                fetch_interval_minutes=1441,
            )


class TestContentResponseSchema:
    """Tests for ContentResponseSchema."""

    def test_content_response_orm_mode(self):
        """Test that from_attributes config allows ORM model conversion."""
        from datetime import datetime

        response = ContentResponseSchema(
            id=1,
            source="rss",
            source_url="https://example.com",
            title="Article",
            pipeline_status="scored",
            quality_score=7.5,
            created_at=datetime.now(),
        )
        assert response.id == 1
        assert response.quality_score == 7.5


class TestContentDetailSchema:
    """Tests for ContentDetailSchema computed fields."""

    def test_full_content_prefers_extracted_text(self):
        """full_content uses extracted_text when available."""
        from datetime import datetime

        detail = ContentDetailSchema(
            id=1,
            source="rss",
            source_url="https://example.com",
            pipeline_status="indexed",
            created_at=datetime.now(),
            extracted_text="extracted",
            raw_text="raw",
        )
        assert detail.full_content == "extracted"

    def test_full_content_falls_back_to_raw_text(self):
        """full_content falls back to raw_text when extracted_text is missing."""
        from datetime import datetime

        detail = ContentDetailSchema(
            id=2,
            source="rss",
            source_url="https://example.com/2",
            pipeline_status="indexed",
            created_at=datetime.now(),
            extracted_text=None,
            raw_text="raw fallback",
        )
        assert detail.full_content == "raw fallback"


class TestPipelineTaskSchema:
    """Tests for PipelineTaskSchema."""

    def test_pipeline_task_valid(self):
        """Test PipelineTaskSchema with valid data."""
        from datetime import datetime

        task = PipelineTaskSchema(
            content_id=1,
            status=PipelineStatus.understood,
            stage="gatekeeper",
            started_at=datetime.now(),
        )
        assert task.content_id == 1
        assert task.status == PipelineStatus.understood

    def test_pipeline_task_with_error(self):
        """Test PipelineTaskSchema with error."""
        task = PipelineTaskSchema(
            content_id=1,
            status=PipelineStatus.failed,
            stage="gatekeeper",
            error="Ollama timeout",
        )
        assert task.error == "Ollama timeout"
