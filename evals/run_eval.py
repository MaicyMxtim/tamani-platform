"""Score the classifier against the golden set.

Sends every golden-set venue through the gateway and reports precision
and recall per vibe tag. Results are appended to evals/results/ as a
timestamped record, so accuracy over time is a saved history.

    python3 evals/run_eval.py [gateway_url]
"""
import json
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

GATEWAY = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001") + "/v1/classify"
KEY = __import__("os").getenv("EVAL_KEY", "dev-local-key")
ROOT = Path(__file__).resolve().parent

golden = [json.loads(l) for l in open(ROOT / "golden_set.jsonl") if l.strip()]
print(f"scoring {len(golden)} venues against {GATEWAY}")

tp = defaultdict(int)
fp = defaultdict(int)
fn = defaultdict(int)
spend = 0.0
predictions = []

for i, row in enumerate(golden):
    req = urllib.request.Request(
        GATEWAY,
        data=json.dumps({"venue_id": f"eval-{row['venue_id']}", "bypass_cache": True,
                         "description": row["description"]}).encode(),
        headers={"x-api-key": KEY, "content-type": "application/json"},
    )
    while True:
        try:
            body = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = int(e.headers.get("retry-after", "30"))
            print(f"  budget throttled, waiting {wait}s")
            time.sleep(wait)
    pred, truth = set(body["vibes"]), set(row["tags"])
    spend += body["cost_usd"]
    predictions.append({"venue_id": row["venue_id"], "pred": sorted(pred),
                        "truth": sorted(truth), "confidence": body["confidence"]})
    for t in pred & truth:
        tp[t] += 1
    for t in pred - truth:
        fp[t] += 1
    for t in truth - pred:
        fn[t] += 1
    if (i + 1) % 25 == 0:
        print(f"  {i+1}/{len(golden)} done")
    time.sleep(0.15)

print(f"\n{'tag':<18} {'precision':>9} {'recall':>7} {'support':>8}")
macro_p = macro_r = n_tags = 0
for t in sorted(set(tp) | set(fp) | set(fn)):
    p = tp[t] / (tp[t] + fp[t]) if tp[t] + fp[t] else 0.0
    r = tp[t] / (tp[t] + fn[t]) if tp[t] + fn[t] else 0.0
    support = tp[t] + fn[t]
    macro_p += p
    macro_r += r
    n_tags += 1
    print(f"{t:<18} {p:>8.0%} {r:>7.0%} {support:>8}")
micro_p = sum(tp.values()) / (sum(tp.values()) + sum(fp.values()))
micro_r = sum(tp.values()) / (sum(tp.values()) + sum(fn.values()))
print(f"\nmicro precision {micro_p:.1%}  micro recall {micro_r:.1%}  "
      f"macro P {macro_p/n_tags:.1%}  macro R {macro_r/n_tags:.1%}  "
      f"spend ${spend:.4f}")

out_dir = ROOT / "results"
out_dir.mkdir(exist_ok=True)
stamp = time.strftime("%Y%m%d-%H%M%S")
result = {
    "timestamp": stamp,
    "micro_precision": round(micro_p, 4), "micro_recall": round(micro_r, 4),
    "spend_usd": round(spend, 4), "n": len(golden),
    "per_tag": {t: {"tp": tp[t], "fp": fp[t], "fn": fn[t]}
                for t in sorted(set(tp) | set(fp) | set(fn))},
    "predictions": predictions,
}
json.dump(result, open(out_dir / f"eval-{stamp}.json", "w"), indent=1)
json.dump(result, open(out_dir / "latest.json", "w"), indent=1)
print(f"saved results/eval-{stamp}.json (and results/latest.json)")
