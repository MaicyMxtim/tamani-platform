"""
The enrichment agent, running under the governance runtime.

Workflow per venue: look the venue up, classify it through the gateway,
then either write the classification (confidence above threshold) or
queue it for human review. Every step is a governed tool call.

    python agent.py --venue <id> [--dry-run]
    python agent.py --untagged [--dry-run] [--limit N]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import httpx
import redis as redis_lib

import sys as _sys; from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
from governance import GovernanceViolation, Governor

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8001")
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "dev-local-key")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
VENUES_FILE = os.getenv("VENUES_FILE", "/venues.json")

MANIFEST = json.load(open(Path(__file__).parent / "manifest.json"))
r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
_venues = {v["id"]: v for v in json.load(open(VENUES_FILE))}


def lookup_venue(venue_id: str) -> dict:
    v = _venues.get(venue_id)
    if not v:
        raise ValueError(f"unknown venue {venue_id}")
    return v


def classify(venue_id: str, description: str) -> dict:
    resp = httpx.post(
        f"{GATEWAY}/v1/classify",
        json={"venue_id": venue_id, "description": description},
        headers={"x-api-key": GATEWAY_KEY},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def write_classification(venue_id: str, vibes: list, confidence: float,
                         model: str, prompt_version: str) -> dict:
    r.hset("classifications", venue_id, json.dumps({
        "vibes": vibes, "confidence": confidence,
        "model": model, "prompt_version": prompt_version,
    }))
    return {"written": venue_id}


def queue_review(venue_id: str, vibes: list, confidence: float) -> dict:
    r.lpush("review:queue", json.dumps(
        {"venue_id": venue_id, "suggested": vibes, "confidence": confidence}))
    return {"queued": venue_id}


TOOLS = {
    "lookup_venue": (lookup_venue, False),
    "classify": (classify, False),          # spend, but no data mutation
    "write_classification": (write_classification, True),
    "queue_review": (queue_review, True),
}


def enrich(gov: Governor, venue_id: str):
    v = gov.call("lookup_venue", venue_id=venue_id)
    description = (f"{v['name']}. Type: {v.get('type_label') or 'unknown'}. "
                   f"Area: {v.get('area') or 'unknown'}. "
                   f"Price: {v.get('band_label') or 'unknown'}. "
                   f"Rating: {v.get('rating')} from {v.get('rating_count')} reviews.")
    c = gov.call("classify", venue_id=venue_id, description=description)
    if isinstance(c, dict) and c.get("dry_run"):
        return
    if c["confidence"] >= MANIFEST["confidence_threshold"]:
        gov.call("write_classification", venue_id=venue_id, vibes=c["vibes"],
                 confidence=c["confidence"], model=c["model"],
                 prompt_version=c["prompt_version"])
    else:
        gov.call("queue_review", venue_id=venue_id,
                 vibes=c["vibes"], confidence=c["confidence"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue")
    ap.add_argument("--untagged", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gov = Governor(MANIFEST, TOOLS, dry_run=args.dry_run)
    targets = ([args.venue] if args.venue else
               [v["id"] for v in _venues.values() if not v.get("tags")][:args.limit])
    try:
        for vid in targets:
            enrich(gov, vid)
    except GovernanceViolation as exc:
        print(json.dumps({"run": "terminated", "reason": str(exc)}), flush=True)
    print(json.dumps({"run_summary": gov.finish()}), flush=True)
    sys.exit(0 if gov.status == "complete" else 2)


if __name__ == "__main__":
    main()
