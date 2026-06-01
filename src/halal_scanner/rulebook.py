"""Load and query the curated halal knowledge base."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).parent / "data" / "rulebook.yaml"


@dataclass
class RuleEntry:
    """One ingredient ruling from the knowledge base."""
    key: str
    nature: str                      # always_halal | always_haram | source_dependent
    reason: str
    citation: str
    default: str = "shubhah"
    synonyms: list[str] = field(default_factory=list)
    halal_if: list[str] = field(default_factory=list)
    haram_if: list[str] = field(default_factory=list)


class Rulebook:
    """In-memory index of ingredient rulings with flexible matching."""

    def __init__(self, entries: list[RuleEntry]):
        self._entries = entries
        # Map every term (key + synonyms) to its entry.
        self._index: dict[str, RuleEntry] = {}
        for entry in entries:
            for term in [entry.key, *entry.synonyms]:
                self._index[term] = entry

    @classmethod
    def load_default(cls) -> "Rulebook":
        return cls.load_from(_DEFAULT_PATH)

    @classmethod
    def load_from(cls, path: Path) -> "Rulebook":
        try:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed rulebook YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("Rulebook must be a mapping of ingredient -> ruling.")
        entries = []
        for key, data in raw.items():
            entries.append(RuleEntry(
                key=key,
                nature=data["nature"],
                reason=data.get("reason", ""),
                citation=data.get("citation", ""),
                default=data.get("default", "shubhah"),
                synonyms=data.get("synonyms", []) or [],
                halal_if=data.get("halal_if", []) or [],
                haram_if=data.get("haram_if", []) or [],
            ))
        return cls(entries)

    def lookup(self, text: str) -> RuleEntry | None:
        """Find the ruling for normalized `text`.

        Tries exact term match first, then word-subset match (every word of
        a term appears in the text), preferring the longest matching term.
        """
        if text in self._index:
            return self._index[text]
        tokens = set(text.split())
        best_len = -1
        best: RuleEntry | None = None
        for term, entry in self._index.items():
            term_tokens = term.split()
            if all(t in tokens for t in term_tokens):
                if len(term) > best_len:
                    best_len = len(term)
                    best = entry
        return best
