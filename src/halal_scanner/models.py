"""Shared data shapes used across the engine."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    """The three possible classifications."""
    HALAL = "halal"
    HARAM = "haram"
    SHUBHAH = "shubhah"


class Source(str, Enum):
    """Where a classification came from."""
    RULEBOOK = "rulebook"
    GEMMA = "gemma"


class Confidence(str, Enum):
    """How much to trust a classification."""
    HIGH = "high"
    LOW = "low"


@dataclass
class IngredientResult:
    """The classification of one ingredient."""
    input: str          # original string as given
    canonical: str      # normalized form used for lookup
    status: Status
    source: Source
    confidence: Confidence
    reason: str
    citation: str


@dataclass
class ScanVerdict:
    """The overall result for a list of ingredients."""
    verdict: Status
    ingredients: list[IngredientResult]
    summary: str
    disclaimer: str
