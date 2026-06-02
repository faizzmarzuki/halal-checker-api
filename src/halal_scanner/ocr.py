"""Extract ingredient text from a label photo via OCR.

Like the other data sources (``GemmaClient``, ``OpenFoodFactsClient``), the OCR
engine never raises to the caller — any failure collapses to an empty string.

The OCR backend is injectable: the default uses Tesseract via ``pytesseract`` and
``Pillow``, imported lazily so those heavy dependencies (and the system
``tesseract`` binary) are only needed when actually running OCR, never for import
or tests. Tests pass a trivial fake backend instead.
"""
from __future__ import annotations

from typing import Callable

# A backend takes the raw image bytes and returns the recognized text.
OcrBackend = Callable[[bytes], str]


def _default_backend(image_bytes: bytes) -> str:
    """Tesseract OCR backend. Imports are lazy so deps are optional."""
    import io

    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)))


class OcrEngine:
    """Runs OCR on image bytes. Never raises — returns '' on any failure."""

    def __init__(self, backend: OcrBackend | None = None):
        self._backend = backend or _default_backend

    def extract_text(self, image_bytes: bytes) -> str:
        """Return the OCR'd text, stripped, or '' if OCR fails."""
        try:
            return self._backend(image_bytes).strip()
        except Exception:
            return ""


def parse_ingredients(text: str) -> list[str]:
    """Split OCR'd label text into ingredient strings.

    Labels arrive as multiple lines, each possibly holding several
    comma/semicolon-separated ingredients. Split on all of those, strip each
    piece, and drop empties. The engine's normalizer cleans each piece further.
    """
    parts: list[str] = []
    for line in text.splitlines():
        for piece in line.replace(";", ",").split(","):
            piece = piece.strip()
            if piece:
                parts.append(piece)
    return parts
