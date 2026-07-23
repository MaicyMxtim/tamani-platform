"""Promotion gate: compare the newest eval result to the stored baseline.

Fails (exit 1) if micro precision or recall regresses by more than the
tolerance, blocking the prompt or model change in CI.

    python3 evals/check_gate.py
"""
import json
import sys
from pathlib import Path

TOLERANCE = 0.03  # absolute points

ROOT = Path(__file__).resolve().parent
baseline = json.load(open(ROOT / "baseline.json"))
latest_file = sorted((ROOT / "results").glob("eval-*.json"))[-1]
latest = json.load(open(latest_file))

print(f"baseline: P {baseline['micro_precision']:.1%} R {baseline['micro_recall']:.1%}")
print(f"latest ({latest_file.name}): "
      f"P {latest['micro_precision']:.1%} R {latest['micro_recall']:.1%}")

failures = []
for metric in ("micro_precision", "micro_recall"):
    if latest[metric] < baseline[metric] - TOLERANCE:
        failures.append(f"{metric} regressed beyond {TOLERANCE:.0%} tolerance")

if failures:
    print("GATE FAILED: " + "; ".join(failures))
    sys.exit(1)
print("GATE PASSED")
