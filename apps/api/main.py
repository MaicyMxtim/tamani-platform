"""
Tamani API — venue search, filtering and the public feed.

Phase 1 standard: split health probes, structured JSON logging with a
correlation id propagated across service boundaries, Prometheus metrics.
Data is served from Postgres when DATABASE_URL is set; otherwise it falls
back to the inline sample so the stack runs with zero external setup.
"""
import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, HTTPException, Query, Request
from prometheus_fastapi_instrumentator import Instrumentator

SERVICE_NAME = "tamani-api"
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "correlation_id": correlation_id.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger(SERVICE_NAME)

app = FastAPI(
    title="Tamani API",
    description="Intent-first restaurant and bar discovery.",
    version="2.0.0",
)

SAMPLE_VENUES = [
    {"id": "sample-1", "name": "The Salt Room", "area": "Brighton Seafront",
     "type_label": "Seafood", "tags": ["special-occasion", "sit-down", "drinks"]},
    {"id": "sample-2", "name": "Flour Pot Bakery", "area": "Sydney Street",
     "type_label": "Cafe", "tags": ["coffee", "quick", "work-friendly", "brunch"]},
]

_VENUES_CACHE: list[dict] | None = None


def _static_venues() -> list[dict]:
    """Load the bundled snapshot once. Falls back to the inline sample."""
    global _VENUES_CACHE
    if _VENUES_CACHE is None:
        path = os.getenv("VENUES_FILE", "/app/data/venues.static.json")
        try:
            with open(path) as f:
                _VENUES_CACHE = json.load(f)
            log.info("loaded %d venues from %s", len(_VENUES_CACHE), path)
        except OSError:
            log.warning("no static venue file at %s, using inline sample", path)
            _VENUES_CACHE = SAMPLE_VENUES
    return _VENUES_CACHE

_started_at = time.monotonic()
STARTUP_GRACE_SECONDS = float(os.getenv("STARTUP_GRACE_SECONDS", "0"))


@app.middleware("http")
async def correlation(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
    correlation_id.set(cid)
    response = await call_next(request)
    response.headers["x-correlation-id"] = cid
    return response


@app.get("/", include_in_schema=False)
def root():
    """Friendly landing so the bare domain isn't a 404."""
    return {
        "service": SERVICE_NAME,
        "status": "live",
        "venues": len(_static_venues()),
        "try": {
            "interactive_docs": "/docs",
            "search": "/venues?vibe=late-night",
            "feed": "/feed?limit=10",
        },
    }


@app.get("/health/live")
def liveness():
    """Only proves the process responds. No dependency checks here."""
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/ready")
def readiness():
    """Checks the dependencies this service needs to serve traffic."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return {"status": "ok", "database": "inline-sample"}
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001 - readiness must not crash
        log.warning("readiness failed: %s", exc)
        raise HTTPException(status_code=503, detail="database unreachable")


@app.get("/health/startup")
def startup():
    """Passes once the startup grace period has elapsed."""
    if time.monotonic() - _started_at < STARTUP_GRACE_SECONDS:
        raise HTTPException(status_code=503, detail="starting")
    return {"status": "ok"}


def _load_venues() -> list[dict]:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return _static_venues()
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(
            "SELECT id, name, area, type_label, tags, band, rating FROM venues"
        ).fetchall()


@app.get("/venues")
def venues(
    vibe: str | None = Query(default=None, description="tag filter, e.g. late-night"),
    area: str | None = Query(default=None),
    band: str | None = Query(default=None, description="price band, e.g. under_5"),
    q: str | None = Query(default=None, description="free-text name search"),
    limit: int = Query(default=50, le=500),
):
    result = _load_venues()
    if vibe:
        result = [v for v in result if vibe in (v.get("tags") or [])]
    if area:
        result = [v for v in result if area.lower() in (v.get("area") or "").lower()]
    if band:
        result = [v for v in result if v.get("band") == band]
    if q:
        result = [v for v in result if q.lower() in v["name"].lower()]
    log.info("venue search returned %d results", len(result))
    return {"count": len(result), "venues": result[:limit]}


@app.get("/venues/{venue_id}")
def venue(venue_id: str):
    for v in _load_venues():
        if str(v["id"]) == venue_id:
            return v
    raise HTTPException(status_code=404, detail="venue not found")


@app.get("/feed")
def feed(limit: int = Query(default=20, le=100)):
    """Public feed consumed by the mobile client and the web MVP."""
    ranked = sorted(
        _load_venues(),
        key=lambda v: (v.get("rating") or 0) * (v.get("rating_count") or 0),
        reverse=True,
    )
    return {"venues": ranked[:limit]}


Instrumentator().instrument(app).expose(app, endpoint="/metrics")
