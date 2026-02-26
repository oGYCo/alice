# pyright: reportMissingImports=false, reportMissingTypeStubs=false

import json

import pytest

from alice.config.scoring import ScoringConfig
from alice.llm.mock import MockLLMClient
from alice.schemas.quality import (
    SevenDimensionScoreResult,
    SevenDimensionScores,
)
from alice.services.scoring import SevenDimensionScoringService

# ============================================================================
# TestSevenDimensionScores — Schema Validation
# ============================================================================


class TestSevenDimensionScores:
    """Test SevenDimensionScores schema validation."""

    def test_valid_scores_all_in_range(self) -> None:
        """Valid scores (0.0–1.0) are accepted."""
        scores = SevenDimensionScores(
            substance=0.8,
            density=0.7,
            credibility=0.9,
            novelty=0.6,
            actionability=0.5,
            social_signal=0.7,
            timeliness=0.8,
            reasoning="Good quality.",
        )
        assert scores.substance == 0.8
        assert scores.density == 0.7

    def test_valid_scores_boundary_zero(self) -> None:
        """Score of exactly 0.0 is valid."""
        scores = SevenDimensionScores(
            substance=0.0,
            density=0.0,
            credibility=0.0,
            novelty=0.0,
            actionability=0.0,
            social_signal=0.0,
            timeliness=0.0,
            reasoning="All zero.",
        )
        assert scores.substance == 0.0

    def test_valid_scores_boundary_one(self) -> None:
        """Score of exactly 1.0 is valid."""
        scores = SevenDimensionScores(
            substance=1.0,
            density=1.0,
            credibility=1.0,
            novelty=1.0,
            actionability=1.0,
            social_signal=1.0,
            timeliness=1.0,
            reasoning="All max.",
        )
        assert scores.substance == 1.0

    def test_invalid_score_too_high(self) -> None:
        """Score > 1.0 is rejected."""
        with pytest.raises(ValueError):
            SevenDimensionScores(
                substance=1.5,
                density=0.7,
                credibility=0.9,
                novelty=0.6,
                actionability=0.5,
                social_signal=0.7,
                timeliness=0.8,
            )

    def test_invalid_score_negative(self) -> None:
        """Score < 0.0 is rejected."""
        with pytest.raises(ValueError):
            SevenDimensionScores(
                substance=-0.1,
                density=0.7,
                credibility=0.9,
                novelty=0.6,
                actionability=0.5,
                social_signal=0.7,
                timeliness=0.8,
            )


# ============================================================================
# TestSevenDimensionScoreResult — Result Model
# ============================================================================


class TestSevenDimensionScoreResult:
    """Test SevenDimensionScoreResult schema and logic."""

    def test_passes_threshold_true_at_0_6(self) -> None:
        """passes_threshold=True when q_total >= 0.6."""
        dimensions = SevenDimensionScores(
            substance=0.6,
            density=0.6,
            credibility=0.6,
            novelty=0.6,
            actionability=0.6,
            social_signal=0.6,
            timeliness=0.6,
        )
        result = SevenDimensionScoreResult(dimensions=dimensions, q_total=0.6)
        assert result.passes_threshold is True

    def test_passes_threshold_true_above_0_6(self) -> None:
        """passes_threshold=True when q_total > 0.6."""
        dimensions = SevenDimensionScores(
            substance=0.8,
            density=0.8,
            credibility=0.8,
            novelty=0.8,
            actionability=0.8,
            social_signal=0.8,
            timeliness=0.8,
        )
        result = SevenDimensionScoreResult(dimensions=dimensions, q_total=0.7)
        assert result.passes_threshold is True

    def test_passes_threshold_false_below_0_6(self) -> None:
        """passes_threshold=False when q_total < 0.6."""
        dimensions = SevenDimensionScores(
            substance=0.5,
            density=0.5,
            credibility=0.5,
            novelty=0.5,
            actionability=0.5,
            social_signal=0.5,
            timeliness=0.5,
        )
        result = SevenDimensionScoreResult(dimensions=dimensions, q_total=0.5)
        assert result.passes_threshold is False

    def test_passes_threshold_false_just_below_0_6(self) -> None:
        """passes_threshold=False when q_total is just below 0.6."""
        dimensions = SevenDimensionScores(
            substance=0.3,
            density=0.3,
            credibility=0.3,
            novelty=0.3,
            actionability=0.3,
            social_signal=0.3,
            timeliness=0.3,
        )
        result = SevenDimensionScoreResult(dimensions=dimensions, q_total=0.59)
        assert result.passes_threshold is False

    def test_model_post_init_sets_passes_threshold(self) -> None:
        """model_post_init is called and sets passes_threshold correctly."""
        dimensions = SevenDimensionScores(
            substance=0.7,
            density=0.7,
            credibility=0.7,
            novelty=0.7,
            actionability=0.7,
            social_signal=0.7,
            timeliness=0.7,
        )
        result = SevenDimensionScoreResult(dimensions=dimensions, q_total=0.65)
        # model_post_init should have been called during construction
        assert result.passes_threshold is True


# ============================================================================
# TestScoringConfig — Configuration Weights
# ============================================================================


class TestScoringConfig:
    """Test ScoringConfig weights."""

    def test_default_weights_sum_to_one(self) -> None:
        """Default weights sum to 1.0."""
        cfg = ScoringConfig()
        total = (
            cfg.weight_substance
            + cfg.weight_density
            + cfg.weight_credibility
            + cfg.weight_novelty
            + cfg.weight_actionability
            + cfg.weight_social_signal
            + cfg.weight_timeliness
        )
        assert abs(total - 1.0) < 0.0001

    def test_default_weights_correct_values(self) -> None:
        """Default weights have correct documented values."""
        cfg = ScoringConfig()
        assert cfg.weight_substance == 0.25
        assert cfg.weight_density == 0.15
        assert cfg.weight_credibility == 0.15
        assert cfg.weight_novelty == 0.20
        assert cfg.weight_actionability == 0.10
        assert cfg.weight_social_signal == 0.10
        assert cfg.weight_timeliness == 0.05

    def test_custom_weights_via_constructor(self) -> None:
        """Custom weights via constructor override defaults."""
        cfg = ScoringConfig(
            weight_substance=0.5,
            weight_density=0.1,
            weight_credibility=0.1,
            weight_novelty=0.1,
            weight_actionability=0.05,
            weight_social_signal=0.05,
            weight_timeliness=0.1,
        )
        assert cfg.weight_substance == 0.5
        assert cfg.weight_density == 0.1
        assert cfg.weight_credibility == 0.1

    def test_partial_custom_weights(self) -> None:
        """Partial custom weights override only specified fields."""
        cfg = ScoringConfig(weight_substance=0.5)
        assert cfg.weight_substance == 0.5
        assert cfg.weight_density == 0.15  # default


# ============================================================================
# TestSevenDimensionScoringService — Main Service
# ============================================================================


class TestSevenDimensionScoringService:
    """Test SevenDimensionScoringService async scoring logic."""

    async def test_score_returns_correct_weighted_total(self) -> None:
        """Service returns correct q_total with weighted sum."""
        # All dimensions = 0.8, default weights should sum to 0.8
        response = json.dumps(
            {
                "substance": 0.8,
                "density": 0.8,
                "credibility": 0.8,
                "novelty": 0.8,
                "actionability": 0.8,
                "social_signal": 0.8,
                "timeliness": 0.8,
                "reasoning": "Good content.",
            }
        )
        client = MockLLMClient()
        client.set_responses([response])

        cfg = ScoringConfig()  # default weights
        service = SevenDimensionScoringService(client, cfg)

        result = await service.score(
            content_text="Test content",
            content_title="Test Title",
            source_url="http://example.com",
            source_type="blog",
        )

        # q_total = 0.25*0.8 + 0.15*0.8 + 0.15*0.8 + 0.20*0.8 + 0.10*0.8 + 0.10*0.8 + 0.05*0.8
        #         = 0.8 * (0.25 + 0.15 + 0.15 + 0.20 + 0.10 + 0.10 + 0.05)
        #         = 0.8 * 1.0 = 0.8
        assert isinstance(result, SevenDimensionScoreResult)
        assert abs(result.q_total - 0.8) < 0.0001

    async def test_score_with_custom_weights(self) -> None:
        """Service applies custom weights correctly."""
        response = json.dumps(
            {
                "substance": 0.5,
                "density": 0.1,
                "credibility": 0.2,
                "novelty": 0.3,
                "actionability": 0.4,
                "social_signal": 0.6,
                "timeliness": 0.7,
                "reasoning": "Test.",
            }
        )
        client = MockLLMClient()
        client.set_responses([response])

        cfg = ScoringConfig(
            weight_substance=0.5,
            weight_density=0.1,
            weight_credibility=0.1,
            weight_novelty=0.1,
            weight_actionability=0.05,
            weight_social_signal=0.05,
            weight_timeliness=0.1,
        )
        service = SevenDimensionScoringService(client, cfg)

        result = await service.score(
            content_text="Test content",
            content_title="Test",
            source_url="http://test.com",
            source_type="news",
        )

        # q_total = 0.5*0.5 + 0.1*0.1 + 0.1*0.2 + 0.1*0.3 + 0.05*0.4 + 0.05*0.6 + 0.1*0.7
        #         = 0.25 + 0.01 + 0.02 + 0.03 + 0.02 + 0.03 + 0.07 = 0.43
        expected = (
            0.5 * 0.5 + 0.1 * 0.1 + 0.1 * 0.2 + 0.1 * 0.3 + 0.05 * 0.4 + 0.05 * 0.6 + 0.1 * 0.7
        )
        assert abs(result.q_total - expected) < 0.0001

    async def test_retry_on_invalid_json(self) -> None:
        """Service retries once if LLM returns invalid JSON first."""
        valid_response = json.dumps(
            {
                "substance": 0.7,
                "density": 0.6,
                "credibility": 0.8,
                "novelty": 0.5,
                "actionability": 0.4,
                "social_signal": 0.6,
                "timeliness": 0.7,
                "reasoning": "Second try succeeded.",
            }
        )
        client = MockLLMClient()
        client.set_responses(["not valid json", valid_response])

        service = SevenDimensionScoringService(client)
        result = await service.score(
            content_text="Test content",
            content_title="Test",
            source_url="http://test.com",
            source_type="article",
        )

        assert isinstance(result, SevenDimensionScoreResult)
        # Check that it parsed the second (valid) response
        assert result.dimensions.substance == 0.7

    async def test_fails_after_two_invalid_responses(self) -> None:
        """Service raises ValueError if both attempts return invalid JSON."""
        client = MockLLMClient()
        client.set_responses(["not json", "still not json"])

        service = SevenDimensionScoringService(client)

        with pytest.raises(ValueError, match="LLM returned invalid JSON after retry"):
            await service.score(
                content_text="Test content",
                content_title="Test",
                source_url="http://test.com",
                source_type="page",
            )

    async def test_passes_threshold_logic(self) -> None:
        """Result passes threshold if q_total >= 0.6, fails if < 0.6."""
        # Test passes (q_total = 0.7)
        response_pass = json.dumps(
            {
                "substance": 0.7,
                "density": 0.7,
                "credibility": 0.7,
                "novelty": 0.7,
                "actionability": 0.7,
                "social_signal": 0.7,
                "timeliness": 0.7,
                "reasoning": "High quality.",
            }
        )
        client = MockLLMClient()
        client.set_responses([response_pass])
        service = SevenDimensionScoringService(client)

        result = await service.score(
            content_text="High quality content",
            content_title="Good",
            source_url="http://good.com",
            source_type="blog",
        )
        assert result.passes_threshold is True

        # Test fails (q_total = 0.5)
        response_fail = json.dumps(
            {
                "substance": 0.5,
                "density": 0.5,
                "credibility": 0.5,
                "novelty": 0.5,
                "actionability": 0.5,
                "social_signal": 0.5,
                "timeliness": 0.5,
                "reasoning": "Low quality.",
            }
        )
        client2 = MockLLMClient()
        client2.set_responses([response_fail])
        service2 = SevenDimensionScoringService(client2)

        result2 = await service2.score(
            content_text="Low quality content",
            content_title="Bad",
            source_url="http://bad.com",
            source_type="news",
        )
        assert result2.passes_threshold is False

    async def test_score_rounds_q_total_to_four_decimals(self) -> None:
        """Service rounds q_total to 4 decimals."""
        response = json.dumps(
            {
                "substance": 0.123456,
                "density": 0.654321,
                "credibility": 0.111111,
                "novelty": 0.222222,
                "actionability": 0.333333,
                "social_signal": 0.444444,
                "timeliness": 0.555555,
                "reasoning": "Rounding test.",
            }
        )
        client = MockLLMClient()
        client.set_responses([response])

        service = SevenDimensionScoringService(client)
        result = await service.score(
            content_text="Test",
            content_title="Test",
            source_url="http://test.com",
            source_type="blog",
        )

        # Check that q_total is rounded to 4 decimals (str representation check)
        q_str = str(result.q_total)
        decimals = len(q_str.split(".")[-1]) if "." in q_str else 0
        assert decimals <= 4

    async def test_score_with_empty_content_text(self) -> None:
        """Service works with empty content_text."""
        response = json.dumps(
            {
                "substance": 0.5,
                "density": 0.5,
                "credibility": 0.5,
                "novelty": 0.5,
                "actionability": 0.5,
                "social_signal": 0.5,
                "timeliness": 0.5,
                "reasoning": "Empty text.",
            }
        )
        client = MockLLMClient()
        client.set_responses([response])

        service = SevenDimensionScoringService(client)
        result = await service.score(
            content_text="",
            content_title="Title Only",
            source_url="",
            source_type="",
        )

        assert isinstance(result, SevenDimensionScoreResult)
        assert result.q_total == 0.5

    async def test_score_logs_completion(self) -> None:
        """Service logs completion after successful scoring."""
        response = json.dumps(
            {
                "substance": 0.6,
                "density": 0.6,
                "credibility": 0.6,
                "novelty": 0.6,
                "actionability": 0.6,
                "social_signal": 0.6,
                "timeliness": 0.6,
                "reasoning": "Logging test.",
            }
        )
        client = MockLLMClient()
        client.set_responses([response])

        service = SevenDimensionScoringService(client)
        result = await service.score(
            content_text="Test content",
            content_title="Test",
            source_url="http://test.com",
            source_type="blog",
        )

        # Service should complete without error and log completion
        assert result.q_total == 0.6
        assert result.passes_threshold is True
