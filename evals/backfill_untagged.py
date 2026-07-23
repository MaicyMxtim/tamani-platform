"""Classify every untagged venue through the gateway. Run from repo root:

    python3 evals/backfill_untagged.py
"""
import json
import time
import urllib.request

GATEWAY = "http://localhost:8001/v1/classify"
KEY = "dev-local-key"

venues = json.load(open("apps/api/data/venues.static.json"))
untagged = [v for v in venues if not v.get("tags")]
print(f"{len(untagged)} untagged venues")

results = []
for v in untagged:
    description = (
        f"{v['name']}. Type: {v.get('type_label') or 'unknown'}. "
        f"Area: {v.get('area') or 'unknown'}. "
        f"Price: {v.get('band_label') or 'unknown'}. "
        f"Rating: {v.get('rating')} from {v.get('rating_count')} reviews."
    )
    req = urllib.request.Request(
        GATEWAY,
        data=json.dumps({"venue_id": v["id"], "description": description}).encode(),
        headers={"x-api-key": KEY, "content-type": "application/json"},
    )
    body = json.load(urllib.request.urlopen(req, timeout=120))
    results.append(body)
    flag = "cache" if body["cached"] else body["model"]
    print(f"{v['name'][:34]:36} -> {','.join(body['vibes']):44} "
          f"conf={body['confidence']:.2f} ${body['cost_usd']:.5f} ({flag})")
    time.sleep(0.2)

spend = sum(r["cost_usd"] for r in results)
hits = sum(1 for r in results if r["cached"])
low_conf = [r for r in results if r["confidence"] < 0.6]
print(f"\ntotal: {len(results)} classified, {hits} cache hits, "
      f"${spend:.4f} spent, {len(low_conf)} low-confidence (needs human review)")
json.dump(results, open("evals/backfill_results.json", "w"), indent=1)
