"""Ollama/Gemma fallback for ingredients not in the rulebook."""
from __future__ import annotations

import json

import requests

from .models import Confidence, IngredientResult, Source, Status

_PROMPT = (
    "You are a halal food analyst. Classify the single ingredient below as "
    "halal, haram, or shubhah (doubtful). Respond with ONLY a JSON object: "
    '{{"status": "halal|haram|shubhah", "reason": "short reason"}}.\n'
    "Ingredient: {ingredient}"
)


class GemmaClient:
    """Calls a local Ollama server. Never raises to the caller."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "gemma3:4b",
        timeout: int = 30,
    ):
        self.host = host
        self.model = model
        self.timeout = timeout

    def classify(self, ingredient_text: str) -> IngredientResult | None:
        """Return a LOW-confidence result, or None on any failure."""
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": _PROMPT.format(ingredient=ingredient_text),
                    "stream": False,
                    "format": "json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = json.loads(resp.json()["response"])
            status = Status(payload["status"])
            reason = str(payload.get("reason", "")).strip()
        except Exception:
            return None
        return IngredientResult(
            input=ingredient_text,
            canonical=ingredient_text,
            status=status,
            source=Source.GEMMA,
            confidence=Confidence.LOW,
            reason=f"{reason} (Gemma estimate — unverified)",
            citation="Gemma (no citation)",
        )
