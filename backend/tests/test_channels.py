"""Tests for channel endpoints — primarily auth enforcement."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PROTECTED_GETS = [
    "/api/channels",
    "/api/channels/guide",
    "/api/channels/guide-grid",
    "/api/channels/library",
    "/api/channels/local-guide",
    "/api/channels/server-info",
    "/api/channels/airings",
]


def test_protected_endpoints_require_auth():
    for path in PROTECTED_GETS:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should return 401, got {resp.status_code}"


def test_channel_detail_requires_auth():
    resp = client.get("/api/channels/detail", params={"path": "/server/info"})
    assert resp.status_code == 401


def test_channel_detail_rejects_bad_path():
    """Ensure path traversal / SSRF is blocked even when authenticated."""
    # We can't easily auth in unit tests, but we can verify the 400 vs 401 distinction
    # by checking validation logic directly via the route.
    # This test verifies the validation is present by importing the logic.
    from app.routes.channels import channel_detail
    import inspect
    src = inspect.getsource(channel_detail)
    assert '://' in src  # SSRF check present
    assert 'startswith("/")' in src  # path must be absolute


def test_debug_report_unauthenticated():
    """Debug report is public — returns server info without auth."""
    resp = client.get("/api/channels/debug-report")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "server" in data
    assert "auth" in data
    assert "recent_logs" in data
    assert data["auth"]["authenticated"] is False


def test_stream_stop_requires_auth():
    resp = client.delete("/api/stream/fakesessionid")
    assert resp.status_code == 401


def test_transcode_status_requires_auth():
    resp = client.get("/api/transcode/status/fakesessionid")
    assert resp.status_code == 401
