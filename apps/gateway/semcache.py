"""
Semantic cache: venue descriptions are embedded locally (no API cost) and
compared by cosine similarity against previous classifications. A match
above the threshold returns the stored answer without a provider call.

The embedding model (bge-small-en-v1.5, ~34 MB ONNX) is baked into the
image at build time so the read-only container never downloads anything.
"""
import hashlib
import json
import os

import numpy as np

# Tuned against 400 real venues (evals/tune_threshold.py): at 0.94 the
# sample showed zero false hits with a 5.5% ambient hit rate; 0.90 nearly
# tripled hits but served ~4% wrong answers. Accuracy wins.
THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.94"))

_model = None


def _embedder():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model


def embed(text: str) -> np.ndarray:
    vec = next(iter(_embedder().embed([text])))
    return vec / np.linalg.norm(vec)


def _key(prompt_version: str) -> str:
    return f"semcache:{prompt_version}"


def lookup(r, prompt_version: str, vec: np.ndarray) -> tuple[dict | None, float]:
    """Return (cached body, similarity) of the best match, or (None, best)."""
    best_body, best_sim = None, 0.0
    for raw in r.hvals(_key(prompt_version)):
        entry = json.loads(raw)
        sim = float(np.dot(vec, np.asarray(entry["vec"], dtype=np.float32)))
        if sim > best_sim:
            best_sim = sim
            best_body = entry["body"]
    if best_sim >= THRESHOLD:
        return best_body, best_sim
    return None, best_sim


def store(r, prompt_version: str, text: str, vec: np.ndarray, body: dict):
    field = hashlib.sha256(text.encode()).hexdigest()
    r.hset(_key(prompt_version), field, json.dumps(
        {"vec": [round(float(x), 6) for x in vec], "body": body}
    ))
