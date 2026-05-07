"""Tests for stream endpoint security."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_start_stream_requires_auth():
    resp = client.post("/api/stream/some-channel-id")
    assert resp.status_code == 401


def test_hls_proxy_unknown_session():
    """Unknown session should 404, not 500."""
    resp = client.get("/api/hls/deadbeef/playlist.m3u8")
    assert resp.status_code == 404


def test_transcoded_rejects_non_hex_session():
    """Non-hex session ID should be rejected to prevent path traversal."""
    resp = client.get("/api/transcoded/../../../etc/passwd/playlist.m3u8")
    assert resp.status_code in (400, 404, 422)


def test_transcoded_rejects_traversal_in_path():
    """Path traversal attempt in the file path should be rejected."""
    valid_hex = "abcdef1234567890abcdef1234567890"
    resp = client.get(f"/api/transcoded/{valid_hex}/../../etc/passwd")
    assert resp.status_code in (400, 404)
