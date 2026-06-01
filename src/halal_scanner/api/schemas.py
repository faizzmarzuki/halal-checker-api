"""Pydantic request/response models for the API.

These define the JSON shapes at the HTTP boundary and are kept separate from
the engine's internal dataclasses (in models.py) so the wire format can evolve
independently of the engine.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..models import IngredientResult, ScanVerdict


class ClassifyRequest(BaseModel):
    """Body for POST /classify."""
    # min_length=1 => an empty list is rejected with HTTP 422 automatically.
    ingredients: list[str] = Field(..., min_length=1)
    use_gemma: bool = True


class IngredientOut(BaseModel):
    """One classified ingredient, serialized for the wire."""
    input: str
    canonical: str
    status: str
    source: str
    confidence: str
    reason: str
    citation: str

    @classmethod
    def from_result(cls, r: IngredientResult) -> "IngredientOut":
        # Enums are (str, Enum), so .value gives the plain string.
        return cls(
            input=r.input,
            canonical=r.canonical,
            status=r.status.value,
            source=r.source.value,
            confidence=r.confidence.value,
            reason=r.reason,
            citation=r.citation,
        )


class VerdictOut(BaseModel):
    """Response for POST /classify."""
    verdict: str
    ingredients: list[IngredientOut]
    summary: str
    disclaimer: str

    @classmethod
    def from_verdict(cls, v: ScanVerdict) -> "VerdictOut":
        return cls(
            verdict=v.verdict.value,
            ingredients=[IngredientOut.from_result(r) for r in v.ingredients],
            summary=v.summary,
            disclaimer=v.disclaimer,
        )


class HealthOut(BaseModel):
    """Response for GET /health."""
    status: str
    ollama_available: bool
