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


def test_resolve_tesseract_prefers_explicit_env():
    from halal_scanner.ocr import _resolve_tesseract_cmd

    env = {"HALAL_TESSERACT_CMD": r"D:\tess\tesseract.exe"}
    got = _resolve_tesseract_cmd(
        env, which=lambda _: r"C:\onpath\tesseract.exe", exists=lambda p: True
    )
    assert got == r"D:\tess\tesseract.exe"


def test_resolve_tesseract_none_when_on_path():
    from halal_scanner.ocr import _resolve_tesseract_cmd

    # Already discoverable on PATH -> no override needed.
    got = _resolve_tesseract_cmd(
        {}, which=lambda _: "/usr/bin/tesseract", exists=lambda p: False
    )
    assert got is None


def test_resolve_tesseract_finds_windows_install_off_path():
    from halal_scanner.ocr import _resolve_tesseract_cmd

    expected = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    env = {"ProgramFiles": r"C:\Program Files"}
    got = _resolve_tesseract_cmd(
        env, which=lambda _: None, exists=lambda p: p == expected
    )
    assert got == expected


def test_resolve_tesseract_none_when_not_found():
    from halal_scanner.ocr import _resolve_tesseract_cmd

    got = _resolve_tesseract_cmd({}, which=lambda _: None, exists=lambda p: False)
    assert got is None


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
