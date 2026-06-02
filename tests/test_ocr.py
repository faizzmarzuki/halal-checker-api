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
