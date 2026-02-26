"""Content quality scoring schemas."""

# pyright: reportMissingImports=false, reportImplicitOverride=false

from pydantic import BaseModel, Field


class QualityScoreSchema(BaseModel):
    """Quality score for a content item."""

    score: float = Field(ge=1.0, le=10.0)
    reasoning: str
    passes_threshold: bool = False  # score >= 6.0

    def model_post_init(self, __context: object) -> None:
        """Set passes_threshold based on score."""
        self.passes_threshold = self.score >= 6.0


class SevenDimensionScores(BaseModel):
    """Raw scores for each quality dimension (0.0–1.0)."""

    substance: float = Field(ge=0.0, le=1.0)
    density: float = Field(ge=0.0, le=1.0)
    credibility: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    social_signal: float = Field(ge=0.0, le=1.0)
    timeliness: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class SevenDimensionScoreResult(BaseModel):
    """Result from 7-dimension quality scoring."""

    dimensions: SevenDimensionScores
    q_total: float  # weighted sum, 0.0–1.0
    passes_threshold: bool = False  # q_total >= 0.6

    def model_post_init(self, __context: object) -> None:
        self.passes_threshold = self.q_total >= 0.6
