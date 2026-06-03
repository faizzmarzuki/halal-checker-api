"""Extract ingredient text from a label photo via OCR.

Like the other data sources (``GemmaClient``, ``OpenFoodFactsClient``), the OCR
engine never raises to the caller — any failure collapses to an empty string.

The OCR backend is injectable: the default uses Tesseract via ``pytesseract`` and
``Pillow``, imported lazily so those heavy dependencies (and the system
``tesseract`` binary) are only needed when actually running OCR, never for import
or tests. Tests pass a trivial fake backend instead.
"""
from __future__ import annotations

import os
import shutil
from typing import Callable

# A backend takes the raw image bytes and returns the recognized text.
OcrBackend = Callable[[bytes], str]


def _resolve_tesseract_cmd(env, which=shutil.which, exists=os.path.exists):
    """Return a tesseract executable path to set on pytesseract, or None.

    pytesseract shells out to the ``tesseract`` binary, which on Windows is
    commonly installed (e.g. ``C:\\Program Files\\Tesseract-OCR``) but NOT added
    to PATH, so the default lookup fails. Resolution order:

    1. ``HALAL_TESSERACT_CMD`` env var, if it points at an existing file.
    2. ``tesseract`` already on PATH -> return None (no override needed).
    3. Common Windows install locations -> first one that exists.

    Returns None when nothing is found (the caller leaves pytesseract's default,
    and OcrEngine.extract_text turns the resulting failure into "").
    """
    explicit = env.get("HALAL_TESSERACT_CMD")
    if explicit and exists(explicit):
        return explicit
    if which("tesseract"):
        return None
    candidates = []
    for base_var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = env.get(base_var)
        if base:
            candidates.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
    local = env.get("LOCALAPPDATA")
    if local:
        candidates.append(
            os.path.join(local, "Programs", "Tesseract-OCR", "tesseract.exe")
        )
    candidates += [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for cand in candidates:
        if exists(cand):
            return cand
    return None


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

    Scope of the guard: it checks the canvas dimensions of a single frame.
    Pillow's own ``Image.MAX_IMAGE_PIXELS`` may also fire first; this is the
    project-level cap. For animated formats (GIF/APNG) only the per-frame canvas
    is checked — a many-frame file could exceed the cap in aggregate, but
    pytesseract OCRs frame 0 only, so that is not a decode-amplification path
    here.
    """
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    _ensure_within_pixel_cap(img.width, img.height, max_pixels)
    return img


def _default_backend(image_bytes: bytes) -> str:
    """Tesseract OCR backend. Imports are lazy so deps are optional."""
    import pytesseract

    # Point pytesseract at the engine if it's installed but not on PATH (common
    # on Windows). No-op when already on PATH or not found.
    cmd = _resolve_tesseract_cmd(os.environ)
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
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
