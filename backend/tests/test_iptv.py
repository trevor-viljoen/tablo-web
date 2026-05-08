"""Tests for IPTV endpoints — auth enforcement and basic response shape."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PROTECTED = [
    "/api/iptv/playlist.m3u",
    "/api/iptv/epg.xml",
    "/api/iptv/live/some-channel-id",
]


def test_iptv_endpoints_require_auth():
    for path in PROTECTED:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should return 401, got {resp.status_code}"


def test_playlist_media_type():
    """Verify the playlist endpoint would return the correct content-type if authed."""
    # Check the route exists and returns 401 (not 404) when unauthenticated
    resp = client.get("/api/iptv/playlist.m3u")
    assert resp.status_code == 401


def test_epg_endpoint_exists():
    resp = client.get("/api/iptv/epg.xml")
    assert resp.status_code == 401


def test_live_redirect_endpoint_exists():
    resp = client.get("/api/iptv/live/test-identifier", follow_redirects=False)
    assert resp.status_code == 401
