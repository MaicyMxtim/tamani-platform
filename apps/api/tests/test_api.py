from fastapi.testclient import TestClient

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os

os.environ["VENUES_FILE"] = str(
    Path(__file__).resolve().parents[1] / "data" / "venues.static.json"
)
from main import app  # noqa: E402

client = TestClient(app)


def test_liveness():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness_without_db():
    assert client.get("/health/ready").status_code == 200


def test_static_dataset_loaded():
    r = client.get("/venues", params={"limit": 500})
    assert r.status_code == 200
    assert r.json()["count"] > 1000  # the real snapshot, not the sample


def test_filter_by_vibe():
    body = client.get("/venues", params={"vibe": "late-night"}).json()
    assert body["count"] > 0
    assert all("late-night" in v["tags"] for v in body["venues"])


def test_filter_by_band_and_area():
    body = client.get("/venues", params={"band": "under_5", "area": "lanes"}).json()
    assert all(v["band"] == "under_5" for v in body["venues"])


def test_venue_by_id():
    first = client.get("/venues").json()["venues"][0]
    r = client.get(f"/venues/{first['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == first["name"]


def test_venue_not_found():
    assert client.get("/venues/no-such-id").status_code == 404


def test_feed_ranked():
    venues = client.get("/feed", params={"limit": 10}).json()["venues"]
    assert len(venues) == 10


def test_correlation_id_propagates():
    r = client.get("/venues", headers={"x-correlation-id": "abc123"})
    assert r.headers["x-correlation-id"] == "abc123"
