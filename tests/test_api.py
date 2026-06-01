from unittest.mock import patch

from fastapi.testclient import TestClient

from halal_scanner.api.app import app
from halal_scanner.openfoodfacts import Product

client = TestClient(app)


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


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["ollama_available"], bool)
