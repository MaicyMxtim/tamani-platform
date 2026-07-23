"""
Tamani inference gateway — the only service that talks to an LLM provider.

Request path: tenant auth -> token budget -> semantic cache -> provider
(Anthropic primary, mock fallback behind a circuit breaker) -> cache store
-> cost ledger. Every response carries the prompt version and real cost.
"""
import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

import budget
import provider
import semcache

SERVICE_NAME = "tamani-gateway"
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "correlation_id": correlation_id.get(),
            "message": record.getMessage(),
        })


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger(SERVICE_NAME)

app = FastAPI(title="Tamani Inference Gateway", version="1.0.0")

TENANT_KEYS = {
    k.strip(): t.strip()
    for t, k in (
        pair.split(":", 1)
        for pair in os.getenv("TENANT_KEYS", "dev:dev-local-key").split(",")
        if ":" in pair
    )
}

CACHE_HITS = Counter("gateway_cache_hits_total", "Semantic cache hits")
CACHE_MISSES = Counter("gateway_cache_misses_total", "Semantic cache misses")


def _redis():
    import redis
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


@app.middleware("http")
async def correlation(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
    correlation_id.set(cid)
    response = await call_next(request)
    response.headers["x-correlation-id"] = cid
    return response


def tenant(x_api_key: str = Header(default="")) -> str:
    t = TENANT_KEYS.get(x_api_key)
    if not t:
        raise HTTPException(status_code=401, detail="unknown api key")
    return t


class ClassifyRequest(BaseModel):
    venue_id: str
    description: str = Field(min_length=1, max_length=4000)
    # Evals set this so they measure the model, never the cache.
    bypass_cache: bool = False


class ClassifyResponse(BaseModel):
    venue_id: str
    vibes: list[str]
    confidence: float
    model: str
    prompt_version: str
    cached: bool
    cache_similarity: float
    input_tokens: int
    output_tokens: int
    cost_usd: float


def ledger(r, tenant_id: str, result: dict, cached: bool):
    saved = provider.cost_usd(provider.MODEL, 350, 40) if cached else 0.0
    r.xadd("cost:ledger", {
        "tenant": tenant_id,
        "model": result["model"],
        "purpose": "classification",
        "cached": int(cached),
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "cost_usd": f"{result['cost_usd']:.8f}",
        "saved_usd": f"{saved:.8f}",
    })


@app.post("/v1/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, tenant_id: str = Depends(tenant)):
    r = _redis()

    allowed, retry_after = budget.check(r, tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="token budget exhausted",
            headers={"retry-after": str(retry_after)},
        )

    vec = semcache.embed(req.description)
    hit, similarity = (None, 0.0) if req.bypass_cache else \
        semcache.lookup(r, provider.PROMPT_VERSION, vec)
    if hit is not None:
        CACHE_HITS.inc()
        cached_result = {**hit, "input_tokens": 0, "output_tokens": 0,
                         "cost_usd": 0.0}
        ledger(r, tenant_id, cached_result, cached=True)
        log.info("cache hit (sim=%.3f) for venue %s", similarity, req.venue_id)
        return ClassifyResponse(
            venue_id=req.venue_id, cached=True, cache_similarity=similarity,
            prompt_version=provider.PROMPT_VERSION, **cached_result,
        )

    CACHE_MISSES.inc()
    result = provider.classify(req.description)
    budget.consume(r, tenant_id, result["input_tokens"] + result["output_tokens"])
    # Never cache fallback output: a mock answer served during an outage
    # must not keep being served after the provider recovers.
    if result["model"] != "mock-classifier-v0" and not req.bypass_cache:
        semcache.store(r, provider.PROMPT_VERSION, req.description, vec, {
            "vibes": result["vibes"],
            "confidence": result["confidence"],
            "model": result["model"],
        })
    ledger(r, tenant_id, result, cached=False)
    log.info("classified venue %s via %s ($%.6f)", req.venue_id,
             result["model"], result["cost_usd"])
    return ClassifyResponse(
        venue_id=req.venue_id, cached=False, cache_similarity=similarity,
        prompt_version=provider.PROMPT_VERSION, **result,
    )


@app.get("/v1/costs")
def costs(tenant_id: str = Depends(tenant)):
    """Spend and savings summary from the ledger."""
    r = _redis()
    total = saved = 0.0
    calls = hits = 0
    for _, entry in r.xrange("cost:ledger"):
        calls += 1
        total += float(entry.get("cost_usd", 0))
        saved += float(entry.get("saved_usd", 0))
        hits += int(entry.get("cached", 0))
    misses = calls - hits
    return {
        "requests": calls,
        "cache_hits": hits,
        "cache_hit_rate": round(hits / calls, 4) if calls else 0.0,
        "spend_usd": round(total, 6),
        "saved_usd": round(saved, 6),
        "cost_per_1k_classifications_usd":
            round(total / misses * 1000, 4) if misses else 0.0,
        "effective_cost_per_1k_usd":
            round(total / calls * 1000, 4) if calls else 0.0,
        "model": provider.MODEL,
        "prompt_version": provider.PROMPT_VERSION,
    }


@app.get("/health/live")
def liveness():
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/ready")
def readiness():
    try:
        _redis().ping()
        return {"status": "ok", "redis": "reachable"}
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="redis unreachable")


Instrumentator().instrument(app).expose(app, endpoint="/metrics")
