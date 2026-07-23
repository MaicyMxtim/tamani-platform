"""Semantic cache threshold tuning against real venue data.

For a sample of venues, embed each description, find its nearest
neighbour among the others, and treat tag-set overlap as ground truth:
a neighbour whose tags match well would be a GOOD cache hit; one whose
tags differ would be a FALSE hit. Reports hit rate and false-hit rate at
candidate thresholds. Run inside the gateway container:

    docker compose exec gateway python /app/tune_threshold.py
"""
import json
import sys

import numpy as np
from fastembed import TextEmbedding

venues = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/venues.json"))
tagged = [v for v in venues if v.get("tags")][:400]

texts = [
    f"{v['name']}. Type: {v.get('type_label') or 'unknown'}. "
    f"Area: {v.get('area') or 'unknown'}. Price: {v.get('band_label') or 'unknown'}."
    for v in tagged
]
print(f"embedding {len(texts)} venue descriptions...")
model = TextEmbedding("BAAI/bge-small-en-v1.5")
vecs = np.array(list(model.embed(texts)))
vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

sims = vecs @ vecs.T
np.fill_diagonal(sims, -1)
nearest = sims.argmax(axis=1)
nearest_sim = sims.max(axis=1)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


overlap = np.array([jaccard(tagged[i]["tags"], tagged[j]["tags"])
                    for i, j in enumerate(nearest)])

print(f"\n{'threshold':>9} {'hit rate':>9} {'false hits':>11} {'notes'}")
for t in [0.85, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98]:
    would_hit = nearest_sim >= t
    n_hit = int(would_hit.sum())
    # a false hit: served a cached answer whose true tags barely overlap
    false_hits = int((would_hit & (overlap < 0.5)).sum())
    rate = n_hit / len(tagged)
    false_rate = false_hits / n_hit if n_hit else 0.0
    print(f"{t:>9.2f} {rate:>8.1%} {false_rate:>10.1%}   "
          f"{n_hit} hits, {false_hits} wrong")
print("\nfalse hit = cached answer whose real tags overlap <50% (jaccard)")
