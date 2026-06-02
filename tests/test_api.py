from unittest.mock import patch

import pytest

from halal_scanner.api.security import require_api_key

from fastapi.testclient import TestClient

from halal_scanner.api.app import app
from halal_scanner.openfoodfacts import Product

client = TestClient(app)


@pytest.fixture(autouse=True)
def _bypass_api_key():
    # Scanning auth is now always-on and DB-backed; these tests aren't about
    # auth, so bypass the key check and restore it afterward.
    app.dependency_overrides[require_api_key] = lambda: None
    yield
    app.dependency_overrides.pop(require_api_key, None)


def test_classify_haram():
    resp = client.post("/classify", json={"ingredients": ["lard"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "haram"
    assert body["ingredients"][0]["status"] == "haram"


def test_classify_shubhah_gelatin():
    resp = client.post("/classify", json={"ingredients": ["gelatin"]})
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "shubhah"


def test_classify_worst_status_wins():
    resp = client.post("/classify", json={"ingredients": ["sugar", "lard"]})
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "haram"


def test_classify_rulebook_only_unknown_no_network():
    # use_gemma=false => deterministic, no network. Unknown -> could-not-verify shubhah.
    resp = client.post(
        "/classify",
        json={"ingredients": ["zzunknownzz"], "use_gemma": False},
    )
    assert resp.status_code == 200
    ing = resp.json()["ingredients"][0]
    assert ing["status"] == "shubhah"
    assert "could not verify" in ing["reason"].lower()


def test_classify_includes_disclaimer():
    resp = client.post("/classify", json={"ingredients": ["sugar"]})
    assert "not a religious ruling" in resp.json()["disclaimer"].lower()


def test_classify_empty_list_rejected():
    resp = client.post("/classify", json={"ingredients": []})
    assert resp.status_code == 422


def test_classify_blank_ingredient_string_rejected():
    # The per-item StringConstraints(min_length=1) rejects blank strings.
    resp = client.post("/classify", json={"ingredients": [""]})
    assert resp.status_code == 422


@patch("halal_scanner.api.app._off_client.fetch")
def test_scan_barcode_classifies_product(mock_fetch):
    mock_fetch.return_value = Product(
        barcode="3017620422003",
        name="Nutella",
        ingredients=["sugar", "lard"],
        raw_text="sugar, lard",
    )
    resp = client.post("/scan-barcode", json={"barcode": "3017620422003"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["barcode"] == "3017620422003"
    assert body["product_name"] == "Nutella"
    # worst-status-wins: lard is haram.
    assert body["verdict"] == "haram"


@patch("halal_scanner.api.app._off_client.fetch", return_value=None)
def test_scan_barcode_not_found_returns_404(mock_fetch):
    resp = client.post("/scan-barcode", json={"barcode": "0000000000000"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_scan_barcode_empty_barcode_rejected():
    resp = client.post("/scan-barcode", json={"barcode": ""})
    assert resp.status_code == 422


@patch("halal_scanner.api.app._ocr_engine.extract_text", return_value="sugar\nlard")
def test_scan_image_classifies_label(mock_ocr):
    resp = client.post("/scan-image", content=b"fake-jpeg-bytes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["extracted_text"] == "sugar\nlard"
    # worst-status-wins: lard is haram.
    assert body["verdict"] == "haram"


@patch("halal_scanner.api.app._ocr_engine.extract_text", return_value="")
def test_scan_image_no_text_returns_422(mock_ocr):
    resp = client.post("/scan-image", content=b"not-an-image")
    assert resp.status_code == 422
    assert "could not read" in resp.json()["detail"].lower()


@patch("halal_scanner.api.app._translator.to_english", side_effect=lambda t: {"tocino": "lard"}.get(t, t))
def test_classify_with_translation(mock_tr):
    resp = client.post(
        "/classify",
        json={"ingredients": ["tocino"], "translate": True, "use_gemma": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "haram"
    # The translated string ("lard") is what got classified.
    assert body["ingredients"][0]["input"] == "lard"


def test_classify_no_translation_by_default_does_not_call_translator():
    with patch("halal_scanner.api.app._translator.to_english") as mock_tr:
        resp = client.post("/classify", json={"ingredients": ["sugar"]})
        assert resp.status_code == 200
        mock_tr.assert_not_called()


def test_rate_limit_returns_429_when_exceeded():
    from halal_scanner.api.security import RateLimiter

    with patch("halal_scanner.api.security.limiter", RateLimiter(limit=1, window=60)):
        first = client.post("/classify", json={"ingredients": ["sugar"]})
        second = client.post("/classify", json={"ingredients": ["sugar"]})
        assert first.status_code == 200
        assert second.status_code == 429


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["ollama_available"], bool)


def test_classify_too_many_ingredients_rejected():
    resp = client.post("/classify", json={"ingredients": ["sugar"] * 201})
    assert resp.status_code == 422


def test_classify_overlong_ingredient_string_rejected():
    resp = client.post("/classify", json={"ingredients": ["x" * 201]})
    assert resp.status_code == 422


def test_classify_at_limits_accepted():
    resp = client.post(
        "/classify",
        json={"ingredients": ["x" * 200] * 200, "use_gemma": False},
    )
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "bad",
    ["abc", "0000/../../../admin?x=#", "@evil.com/path", "12345", "1" * 15],
)
def test_scan_barcode_invalid_rejected(bad):
    resp = client.post("/scan-barcode", json={"barcode": bad})
    assert resp.status_code == 422
