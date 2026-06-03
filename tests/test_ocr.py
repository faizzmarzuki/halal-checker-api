import io

import pytest

from halal_scanner.ocr import OcrEngine, parse_ingredients


def test_extract_text_uses_backend_and_strips():
    engine = OcrEngine(backend=lambda b: "  sugar, lard \n")
    assert engine.extract_text(b"imagebytes") == "sugar, lard"


def test_extract_text_backend_error_returns_empty():
    def boom(_: bytes) -> str:
        raise RuntimeError("tesseract not installed")

    engine = OcrEngine(backend=boom)
    assert engine.extract_text(b"imagebytes") == ""


def test_parse_ingredients_splits_newlines_commas_semicolons():
    text = "Sugar, Palm Oil\nHazelnuts; Cocoa\n\n , \nLard"
    assert parse_ingredients(text) == [
        "Sugar",
        "Palm Oil",
        "Hazelnuts",
        "Cocoa",
        "Lard",
    ]


def test_ensure_within_pixel_cap_accepts_within_limit():
    from halal_scanner.ocr import _ensure_within_pixel_cap

    assert _ensure_within_pixel_cap(1000, 1000, max_pixels=1_000_000) is None


def test_ensure_within_pixel_cap_rejects_oversized():
    from halal_scanner.ocr import _ensure_within_pixel_cap

    with pytest.raises(ValueError):
        _ensure_within_pixel_cap(2000, 2000, max_pixels=1_000_000)


def test_open_image_within_cap_returns_image():
    pil_image = pytest.importorskip("PIL.Image")
    from halal_scanner.ocr import _open_image

    buf = io.BytesIO()
    pil_image.new("RGB", (10, 10)).save(buf, format="PNG")
    img = _open_image(buf.getvalue())
    assert img.width == 10 and img.height == 10


def test_open_image_rejects_decompression_bomb():
    pil_image = pytest.importorskip("PIL.Image")
    from halal_scanner.ocr import _open_image

    buf = io.BytesIO()
    pil_image.new("RGB", (100, 100)).save(buf, format="PNG")
    with pytest.raises(ValueError):
        _open_image(buf.getvalue(), max_pixels=9999)
