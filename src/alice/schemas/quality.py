"""Content quality scoring schemas."""

from pydantic import BaseModel, Field


class QualityScoreSchema(BaseModel):
    """Quality score for a content item."""

    score: float = Field(ge=1.0, le=10.0)
    reasoning: str
    passes_threshold: bool = False  # score >= 6.0

    def model_post_init(self, __context: object) -> None:
        """Set passes_threshold based on score."""
        self.passes_threshold = self.score >= 6.0
