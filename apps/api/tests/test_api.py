from fastapi.testclient import TestClient

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402

client = TestClient(app)


def test_liveness():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness_without_db_uses_sample():
    r = client.get("/health/ready")
    assert r.status_code == 200


def test_venue_filter_by_vibe():
    r = client.get("/venues", params={"vibe": "drinks"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert all("drinks" in v["vibes"] for v in body["venues"])


def test_venue_not_found():
    assert client.get("/venues/9999").status_code == 404


def test_correlation_id_propagates():
    r = client.get("/venues", headers={"x-correlation-id": "abc123"})
    assert r.headers["x-correlation-id"] == "abc123"
