"""
Tamani inference gateway — the only service that talks to an LLM provider.

Phase 1 scope: service skeleton with the request path, per-tenant key check,
exact-match cache in Redis, token/cost accounting stub, and a mock provider
so the stack runs end to end with no API key and no spend. Phase 5 replaces
the mock with real providers, semantic caching, quotas, fallback and hedging.
"""
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

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

app = FastAPI(title="Tamani Inference Gateway", version="0.1.0")

# Tenant keys come from the environment for now; External Secrets Operator
# supplies them in-cluster from Phase 8.
TENANT_KEYS = {
    k.strip(): t.strip()
    for t, k in (
        pair.split(":", 1)
        for pair in os.getenv("TENANT_KEYS", "dev:dev-local-key").split(",")
        if ":" in pair
    )
}

VIBE_TAGS = [
    "special-occasion", "sit-down", "drinks", "groups", "late-night",
    "coffee", "quick", "work-friendly", "brunch", "solo-friendly",
]


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
    venue_id: int
    description: str = Field(min_length=1, max_length=4000)


class ClassifyResponse(BaseModel):
    venue_id: int
    vibes: list[str]
    model: str
    prompt_version: str
    cached: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float


def mock_provider(description: str) -> dict:
    """Deterministic stand-in for a real LLM call. Replaced in Phase 5."""
    text = description.lower()
    vibes = [t for t in VIBE_TAGS if t.split("-")[0] in text] or ["sit-down"]
    return {
        "vibes": vibes[:4],
        "model": "mock-classifier-v0",
        "input_tokens": max(1, len(description) // 4),
        "output_tokens": 24,
        "cost_usd": 0.0,
    }


PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v0.1.0")


@app.post("/v1/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, tenant_id: str = Depends(tenant)):
    cache_key = "cls:" + hashlib.sha256(
        f"{PROMPT_VERSION}:{req.description}".encode()
    ).hexdigest()
    r = _redis()

    if (hit := r.get(cache_key)) is not None:
        body = json.loads(hit)
        log.info("cache hit for venue %d tenant %s", req.venue_id, tenant_id)
        return ClassifyResponse(venue_id=req.venue_id, cached=True, **body)

    result = mock_provider(req.description)
    body = {**result, "prompt_version": PROMPT_VERSION}
    r.set(cache_key, json.dumps(body), ex=int(os.getenv("CACHE_TTL", "86400")))

    # Cost accounting: one record per request, attributed to tenant/model/purpose.
    r.xadd("cost:ledger", {
        "tenant": tenant_id,
        "model": result["model"],
        "purpose": "classification",
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "cost_usd": result["cost_usd"],
    })
    log.info("classified venue %d for tenant %s", req.venue_id, tenant_id)
    return ClassifyResponse(venue_id=req.venue_id, cached=False, **body)


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
