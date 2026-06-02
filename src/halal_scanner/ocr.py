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


# Bound the decoded pixel area to defend against decompression bombs (MED-2).
# ~40 MP is generous for a real phone photo of a label; bombs are typically
# hundreds of MP. OcrEngine.extract_text already turns any failure into "".
MAX_IMAGE_PIXELS = 40_000_000


def _ensure_within_pixel_cap(
    width: int, height: int, max_pixels: int = MAX_IMAGE_PIXELS
) -> None:
    """Raise ValueError if the decoded pixel area would exceed the cap (MED-2)."""
    if width * height > max_pixels:
        raise ValueError(f"image {width}x{height} exceeds {max_pixels}px cap")


def _open_image(image_bytes: bytes, max_pixels: int = MAX_IMAGE_PIXELS):
    """Open image bytes with Pillow, rejecting oversized (bomb) images.

    Image.open is lazy (reads the header only), so width/height are available
    before the pixels are decoded — the check rejects a bomb before any large
    allocation happens.
    """
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    _ensure_within_pixel_cap(img.width, img.height, max_pixels)
    return img


def _default_backend(image_bytes: bytes) -> str:
    """Tesseract OCR backend. Imports are lazy so deps are optional."""
    import pytesseract

    return pytesseract.image_to_string(_open_image(image_bytes))


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
