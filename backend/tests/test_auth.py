"""Tests for auth endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_status_unauthenticated():
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["devices"] == []
    assert data["active_sid"] is None
    assert "email" in data


def test_login_bad_credentials():
    resp = client.post("/api/auth/login", json={"email": "bad@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
