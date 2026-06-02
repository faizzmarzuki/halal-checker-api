from unittest.mock import MagicMock, patch

from halal_scanner.translator import Translator


def _fake_response(text):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"response": text}
    return resp


@patch("halal_scanner.translator.requests.post")
def test_to_english_success(mock_post):
    mock_post.return_value = _fake_response("  pork lard\n")
    assert Translator().to_english("manteca de cerdo") == "pork lard"


@patch("halal_scanner.translator.requests.post", side_effect=Exception("conn refused"))
def test_to_english_network_error_returns_original(mock_post):
    assert Translator().to_english("manteca de cerdo") == "manteca de cerdo"


@patch("halal_scanner.translator.requests.post")
def test_to_english_blank_input_returns_unchanged_without_calling(mock_post):
    assert Translator().to_english("   ") == "   "
    mock_post.assert_not_called()
