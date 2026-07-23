"""Model tiering experiment.

Runs the golden set through each candidate model directly (bypassing the
gateway cache) and reports accuracy and cost per model, so the accuracy
cost of routing cheap-vs-expensive is measured, not assumed.

    ANTHROPIC_API_KEY=... python3 evals/tiering_experiment.py
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "apps" / "gateway"))
import provider  # noqa: E402 — reuse the schema, prompt and pricing

MODELS = ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-4-8"]
golden = [json.loads(l) for l in open(ROOT / "golden_set.jsonl") if l.strip()]
client = anthropic.Anthropic()


def classify(model: str, description: str) -> tuple[set, float, float]:
    resp = client.messages.create(
        model=model, max_tokens=1024, system=provider.SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": provider.OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": description}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    body = json.loads(text)
    cost = provider.cost_usd(model, resp.usage.input_tokens, resp.usage.output_tokens)
    return set(body["vibes"]), body["confidence"], cost


results = {}
for model in MODELS:
    tp = fp = fn = 0
    spend = 0.0
    print(f"\n== {model} ==")
    for i, row in enumerate(golden):
        for attempt in range(6):
            try:
                pred, _conf, cost = classify(model, row["description"])
                break
            except anthropic.RateLimitError:
                time.sleep(20)
        else:
            continue
        truth = set(row["tags"])
        tp += len(pred & truth); fp += len(pred - truth); fn += len(truth - pred)
        spend += cost
        if (i + 1) % 40 == 0:
            print(f"  {i+1}/{len(golden)}")
        time.sleep(0.1)
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * p * r / (p + r) if p + r else 0
    results[model] = {"precision": round(p, 4), "recall": round(r, 4),
                      "f1": round(f1, 4), "spend_usd": round(spend, 4),
                      "cost_per_1k_usd": round(spend / len(golden) * 1000, 2)}
    print(f"  P {p:.1%}  R {r:.1%}  F1 {f1:.1%}  ${spend:.4f}  "
          f"(${results[model]['cost_per_1k_usd']}/1k)")

json.dump(results, open(ROOT / "tiering_results.json", "w"), indent=1)
print("\n" + json.dumps(results, indent=1))
