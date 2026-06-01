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
    reason: str = ""
    citation: str = ""
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
        """Find the ruling for a SINGLE normalized ingredient string.

        Contract: `text` is expected to be ONE ingredient (already passed
        through `normalize`), e.g. "gelatin" or "pork gelatin" — not a whole
        comma-separated ingredient list. Splitting a list into individual
        ingredients is the caller's responsibility (an upstream concern).

        Matching: exact term match first; otherwise a word-subset match where
        every word of an indexed term must appear among the text's tokens.
        When several terms match, the most SPECIFIC wins — most words, then
        longest, then alphabetical — so "pork gelatin" resolves to the
        `gelatin` entry (whose haram_if then flags the pork source), rather
        than the bare `pork` entry. The winner is deterministic regardless of
        rulebook ordering.
        """
        if text in self._index:
            return self._index[text]
        tokens = set(text.split())
        matches = [
            term for term in self._index
            if all(word in tokens for word in term.split())
        ]
        if not matches:
            return None
        winner = max(matches, key=lambda t: (len(t.split()), len(t), t))
        return self._index[winner]
