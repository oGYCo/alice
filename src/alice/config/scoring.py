"""Scoring dimension configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringConfig(BaseSettings):
    """Quality scoring dimension weights.

    All weights sum to 1.0:
    0.25 + 0.15 + 0.15 + 0.20 + 0.10 + 0.10 + 0.05 = 1.00
    """

    weight_substance: float = 0.25
    """Content substance and core value (25%)."""

    weight_density: float = 0.15
    """Information density and depth (15%)."""

    weight_credibility: float = 0.15
    """Source credibility and factual accuracy (15%)."""

    weight_novelty: float = 0.20
    """Freshness and novelty factor (20%)."""

    weight_actionability: float = 0.10
    """Practical applicability for user's work (10%)."""

    weight_social_signal: float = 0.10
    """Community engagement and visibility (10%)."""

    weight_timeliness: float = 0.05
    """Time sensitivity and relevance window (5%)."""

    model_config = SettingsConfigDict(env_prefix="SCORING_")
