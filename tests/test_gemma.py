from unittest.mock import MagicMock, patch

from halal_scanner.gemma import GemmaClient
from halal_scanner.models import Status, Source, Confidence


def _fake_response(payload_text):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"response": payload_text}
    return resp


@patch("halal_scanner.gemma.requests.post")
def test_classify_success(mock_post):
    mock_post.return_value = _fake_response(
        '{"status": "haram", "reason": "pork enzyme"}'
    )
    client = GemmaClient()
    result = client.classify("some unknown enzyme")
    assert result is not None
    assert result.status is Status.HARAM
    assert result.source is Source.GEMMA
    assert result.confidence is Confidence.LOW
    assert "pork enzyme" in result.reason


@patch("halal_scanner.gemma.requests.post", side_effect=Exception("conn refused"))
def test_classify_network_error_returns_none(mock_post):
    client = GemmaClient()
    assert client.classify("anything") is None


@patch("halal_scanner.gemma.requests.post")
def test_classify_bad_json_returns_none(mock_post):
    mock_post.return_value = _fake_response("this is not json")
    client = GemmaClient()
    assert client.classify("anything") is None
