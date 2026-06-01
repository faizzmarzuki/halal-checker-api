"""Turn a raw ingredient string into canonical matching text."""
from __future__ import annotations

import re

# Matches an E-number, optionally split by spaces: "e 471" -> groups ("471")
_ENUMBER_SPACED = re.compile(r"\be\s+(\d{3,4})\b")
# Any run of characters that is not a letter or digit.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# One or more spaces.
_WS = re.compile(r"\s+")


def normalize(raw: object) -> str:
    """Return a clean, lowercase, space-separated canonical form.

    Steps: coerce to str, lowercase, turn punctuation into spaces,
    rejoin spaced E-numbers ("e 471" -> "e471"), collapse whitespace.
    Returns "" for empty/None input.
    """
    if not isinstance(raw, str):
        return ""
    text = raw.lower()
    # Replace all punctuation with spaces first.
    text = _NON_ALNUM.sub(" ", text)
    # Rejoin spaced E-numbers (now "e 471" after punctuation removal).
    text = _ENUMBER_SPACED.sub(r"e\1", text)
    # Collapse whitespace and trim.
    text = _WS.sub(" ", text).strip()
    return text
