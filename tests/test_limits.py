import asyncio

import pytest
from fastapi import HTTPException

from halal_scanner.api.app import read_capped_body


class _FakeRequest:
    """Minimal stand-in for starlette Request: .headers + async .stream()."""

    def __init__(self, chunks, headers=None):
        self.headers = headers or {}
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


def test_read_capped_body_under_limit_returns_bytes():
    req = _FakeRequest([b"abc", b"def"])
    body = asyncio.run(read_capped_body(req, max_bytes=1024))
    assert body == b"abcdef"


def test_read_capped_body_stream_exceeds_raises_413():
    # No Content-Length header -> the streaming cap is what catches it.
    req = _FakeRequest([b"x" * 600, b"x" * 600])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_capped_body(req, max_bytes=1000))
    assert exc.value.status_code == 413


def test_read_capped_body_content_length_fast_path_413():
    # Header alone trips the fast-path reject before any chunk is read.
    req = _FakeRequest([], headers={"content-length": "9999"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_capped_body(req, max_bytes=1000))
    assert exc.value.status_code == 413
