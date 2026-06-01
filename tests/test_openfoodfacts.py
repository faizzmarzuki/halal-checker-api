from unittest.mock import MagicMock, patch

from halal_scanner.openfoodfacts import OpenFoodFactsClient, split_ingredients


def _fake_response(payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


@patch("halal_scanner.openfoodfacts.requests.get")
def test_fetch_success(mock_get):
    mock_get.return_value = _fake_response(
        {
            "status": 1,
            "product": {
                "product_name": "Nutella",
                "ingredients_text": "Sugar, Palm Oil, Hazelnuts, Cocoa",
            },
        }
    )
    product = OpenFoodFactsClient().fetch("3017620422003")
    assert product is not None
    assert product.barcode == "3017620422003"
    assert product.name == "Nutella"
    assert product.ingredients == ["Sugar", "Palm Oil", "Hazelnuts", "Cocoa"]


@patch("halal_scanner.openfoodfacts.requests.get")
def test_fetch_product_not_found_returns_none(mock_get):
    mock_get.return_value = _fake_response({"status": 0})
    assert OpenFoodFactsClient().fetch("0000000000000") is None


@patch("halal_scanner.openfoodfacts.requests.get", side_effect=Exception("conn refused"))
def test_fetch_network_error_returns_none(mock_get):
    assert OpenFoodFactsClient().fetch("3017620422003") is None


@patch("halal_scanner.openfoodfacts.requests.get")
def test_fetch_missing_ingredients_returns_none(mock_get):
    mock_get.return_value = _fake_response(
        {"status": 1, "product": {"product_name": "Mystery", "ingredients_text": ""}}
    )
    assert OpenFoodFactsClient().fetch("3017620422003") is None


def test_split_ingredients_splits_strips_and_drops_empties():
    assert split_ingredients("Sugar, Palm Oil ,, Cocoa,") == [
        "Sugar",
        "Palm Oil",
        "Cocoa",
    ]
