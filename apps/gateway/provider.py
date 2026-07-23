"""
LLM providers for the inference gateway.

Anthropic is primary, called through the official SDK with structured
outputs so responses are schema-valid by construction. A circuit breaker
trips after repeated failures and requests fall back to the deterministic
mock, so venue enrichment degrades instead of dying when the provider is
unreachable or the key is missing.
"""
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("tamani-gateway")

VIBE_TAGS = [
    "special-occasion", "sit-down", "drinks", "groups", "late-night",
    "coffee", "quick", "work-friendly", "brunch", "solo-friendly",
]

MODEL = os.getenv("MODEL", "claude-opus-4-8")

# USD per million tokens (input, output)
PRICING = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "mock-classifier-v0": (0.0, 0.0),
}

# Highest-versioned prompt wins; each is an immutable artifact in Git and
# the version is recorded on every classification (and cache namespace).
_PROMPT_FILE = sorted(
    (Path(__file__).parent / "prompts").glob("classify_v*.md"),
    key=lambda p: int(p.stem.rsplit("_v", 1)[-1]),
)[-1]
PROMPT_VERSION = "v" + _PROMPT_FILE.stem.rsplit("_v", 1)[-1]
SYSTEM_PROMPT = _PROMPT_FILE.read_text()

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "vibes": {
            "type": "array",
            "items": {"type": "string", "enum": VIBE_TAGS},
        },
        "confidence": {"type": "number"},
    },
    "required": ["vibes", "confidence"],
    "additionalProperties": False,
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = PRICING.get(model, (0.0, 0.0))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


class CircuitOpen(Exception):
    pass


class Breaker:
    """Trip after `threshold` failures inside `window` seconds."""

    def __init__(self, threshold: int = 3, window: float = 60.0):
        self.threshold = threshold
        self.window = window
        self.failures: list[float] = []

    def record_failure(self):
        now = time.monotonic()
        self.failures = [t for t in self.failures if now - t < self.window]
        self.failures.append(now)

    def record_success(self):
        self.failures.clear()

    @property
    def open(self) -> bool:
        now = time.monotonic()
        self.failures = [t for t in self.failures if now - t < self.window]
        return len(self.failures) >= self.threshold


breaker = Breaker()


def classify_anthropic(description: str) -> dict:
    import anthropic

    if breaker.open:
        raise CircuitOpen("anthropic circuit open")

    client = anthropic.Anthropic()  # key from ANTHROPIC_API_KEY
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            messages=[{"role": "user", "content": description}],
        )
    except (anthropic.APIConnectionError, anthropic.RateLimitError,
            anthropic.InternalServerError) as exc:
        breaker.record_failure()
        raise
    except anthropic.APIStatusError:
        # 4xx: our fault, not the provider's health — don't trip the breaker
        raise

    if response.stop_reason == "refusal":
        breaker.record_success()
        raise ValueError("provider refused the request")

    text = next(b.text for b in response.content if b.type == "text")
    body = json.loads(text)  # schema-valid by construction
    breaker.record_success()
    return {
        "vibes": body["vibes"][:4],
        "confidence": max(0.0, min(1.0, float(body["confidence"]))),
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": cost_usd(MODEL, response.usage.input_tokens,
                             response.usage.output_tokens),
    }


def classify_mock(description: str) -> dict:
    """Deterministic fallback: keyword match, zero cost, low confidence."""
    text = description.lower()
    vibes = [t for t in VIBE_TAGS if t.split("-")[0] in text] or ["sit-down"]
    return {
        "vibes": vibes[:4],
        "confidence": 0.2,
        "model": "mock-classifier-v0",
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }


def classify(description: str) -> dict:
    """Primary provider with fallback. Never raises for provider trouble."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return classify_mock(description)
    try:
        return classify_anthropic(description)
    except CircuitOpen:
        log.warning("circuit open, serving mock fallback")
        return classify_mock(description)
    except Exception as exc:  # noqa: BLE001
        log.error("anthropic call failed (%s), serving mock fallback", exc)
        return classify_mock(description)
