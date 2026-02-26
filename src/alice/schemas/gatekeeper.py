"""Gatekeeper (content filtering) schemas."""

from pydantic import BaseModel, Field


class GatekeeperDecision(BaseModel):
    """Decision from gatekeeper (content filter)."""

    passed: bool
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: str = "ollama"  # "ollama" or "rule-based"
