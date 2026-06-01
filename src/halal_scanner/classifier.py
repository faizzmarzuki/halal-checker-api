"""Orchestrate normalization, rulebook lookup, Gemma fallback, aggregation."""
from __future__ import annotations

from .models import Confidence, IngredientResult, ScanVerdict, Source, Status
from .normalizer import normalize
from .rulebook import RuleEntry, Rulebook

DISCLAIMER = (
    "This is automated guidance, not a religious ruling. "
    "Verify with official halal certification (e.g. JAKIM) before relying on it."
)


def _match_keyword(tokens: set[str], keywords: list[str]) -> str | None:
    """Return the first keyword whose words all appear in tokens."""
    for kw in keywords:
        if all(word in tokens for word in kw.split()):
            return kw
    return None


class HalalClassifier:
    def __init__(self, rulebook: Rulebook, gemma_client=None):
        self.rulebook = rulebook
        self.gemma_client = gemma_client

    def classify(self, ingredients: list) -> ScanVerdict:
        results = [
            self._classify_one(raw)
            for raw in ingredients
            if normalize(raw)  # skip empty / non-string
        ]
        verdict = self._aggregate(results)
        return ScanVerdict(
            verdict=verdict,
            ingredients=results,
            summary=self._summarize(verdict, results),
            disclaimer=DISCLAIMER,
        )

    def _classify_one(self, raw) -> IngredientResult:
        text = normalize(raw)
        entry = self.rulebook.lookup(text)
        if entry is not None:
            return self._from_rulebook(raw, text, entry)
        return self._from_gemma(raw, text)

    def _from_rulebook(self, raw, text, entry: RuleEntry) -> IngredientResult:
        if entry.nature == "always_halal":
            status, reason = Status.HALAL, entry.reason
        elif entry.nature == "always_haram":
            status, reason = Status.HARAM, entry.reason
        else:  # source_dependent
            tokens = set(text.split())
            if _match_keyword(tokens, entry.haram_if):
                status = Status.HARAM
                reason = f"Haram source named. {entry.reason}"
            elif _match_keyword(tokens, entry.halal_if):
                status = Status.HALAL
                reason = f"Halal source named. {entry.reason}"
            else:
                status = Status.SHUBHAH
                reason = entry.reason
        return IngredientResult(
            input=raw, canonical=text, status=status,
            source=Source.RULEBOOK, confidence=Confidence.HIGH,
            reason=reason, citation=entry.citation,
        )

    def _from_gemma(self, raw, text) -> IngredientResult:
        if self.gemma_client is not None:
            result = self.gemma_client.classify(text)
            if result is not None:
                return result
        return IngredientResult(
            input=raw, canonical=text, status=Status.SHUBHAH,
            source=Source.GEMMA, confidence=Confidence.LOW,
            reason="Unknown ingredient and could not verify (Gemma unavailable).",
            citation="N/A",
        )

    @staticmethod
    def _aggregate(results: list[IngredientResult]) -> Status:
        statuses = {r.status for r in results}
        if Status.HARAM in statuses:
            return Status.HARAM
        if Status.SHUBHAH in statuses:
            return Status.SHUBHAH
        return Status.HALAL

    @staticmethod
    def _summarize(verdict: Status, results: list[IngredientResult]) -> str:
        n = len(results)
        return f"Overall verdict: {verdict.value.upper()} based on {n} ingredient(s)."
