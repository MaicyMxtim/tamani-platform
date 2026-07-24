# Tamani Platform — Complete Guide

A single guide that teaches the concepts and builds the platform from an empty directory. Written for a beginner: every technology is explained before it is used, and every file is written out in full with the reason it exists. Work through it in order.

Each phase first explains the ideas it depends on, then builds the files that use them, then verifies the result before the next phase begins.

Create the project directory and start version control:

```bash
mkdir tamani && cd tamani && git init
```

All paths below are relative to this `tamani/` directory.

---

# Phase 0 — Foundation

This phase sets up the project's structure and the tools that keep it tidy. It introduces version control, the idea of a single repository holding everything, and a shortcut file for common commands.

## Version control and Git

Version control records every change made to a set of files: what changed, when, and by whom. It allows any past state to be recovered, changes to be reviewed before they take effect, and many people to work on the same files without overwriting each other. Git is the standard version-control tool. A project tracked by Git is called a repository.

## Monorepos

A monorepo is a single repository that holds everything a project needs: the application code, the infrastructure definitions, the configuration and the documentation. Keeping these together means one recorded change can span code and the infrastructure that runs it, and there is one place to look for anything.

## The command line and Make

The command line runs programs by typing their names. Real projects involve many long commands, which are easy to mistype or forget. A Makefile is a file of named shortcuts: typing `make up` runs whatever the Makefile defines for `up`. This makes the workflow reproducible, because the commands live in the project rather than in memory.

## The project files

The `.gitignore` file lists patterns that Git should not track: build outputs, local secrets, and generated state. This keeps sensitive and disposable files out of the repository.

Create **`.gitignore`**:

```text
__pycache__/
*.pyc
.venv/
.env
*.tfstate*
.terraform/
.DS_Store
.pytest_cache/
node_modules/
terraform.tfvars
results/latest.json
```

The Makefile defines each common operation as a single verb. `make up` starts the whole stack, `make test` runs the tests, `make smoke` checks that services answer. Anyone can run the project without memorising commands.

Create **`Makefile`**:

```text
# Every common operation as a single verb. Reproducible from a clean machine.
.PHONY: up down build test lint smoke logs clean

up:            ## run the full stack locally
	docker compose up --build -d

down:          ## stop the stack
	docker compose down

build:         ## build all images
	docker compose build

test:          ## run unit tests in a container (source mounted; HOME writable for pip --user)
	docker compose run --rm --entrypoint sh -e HOME=/tmp \
		-v "$(CURDIR)/apps/api:/app" api -c \
		"pip install --user -q pytest httpx && python -m pytest tests -q"

lint:          ## run pre-commit hooks against all files
	pre-commit run --all-files

smoke:         ## hit the health endpoints of a running stack
	curl -fsS http://localhost:8000/health/live
	curl -fsS http://localhost:8000/health/ready
	curl -fsS http://localhost:8001/health/live
	curl -fsS -X POST http://localhost:8001/v1/classify \
		-H 'x-api-key: dev-local-key' -H 'content-type: application/json' \
		-d '{"venue_id": "smoke-test", "description": "late night drinks with groups"}'

logs:          ## tail all service logs
	docker compose logs -f

clean:         ## remove containers, volumes and dangling images
	docker compose down -v --remove-orphans
```

Pre-commit hooks run automatically before each commit. These format code, check YAML, and scan for accidentally committed secrets, catching problems at the earliest and cheapest point.

Create **`.pre-commit-config.yaml`**:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
        args: [--allow-multiple-documents]
      - id: check-added-large-files
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.2
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.0
    hooks:
      - id: gitleaks
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.96.2
    hooks:
      - id: terraform_fmt
```

An Architecture Decision Record (ADR) is a short document capturing a significant choice: its context, the options, the decision and its consequences. This first ADR establishes that decisions will be recorded, turning the repository into evidence of reasoning rather than only output.

Create **`docs/adr/0001-record-architecture-decisions.md`**:

```markdown
# ADR 0001: Record architecture decisions

## Status
Accepted

## Context
This project exists to demonstrate judgement, not only artifacts. Each
significant choice needs its context, options, decision and consequences
written down at the time it is made.

## Decision
Every significant choice gets an ADR in this directory, numbered
sequentially, following this template. Planned records, per the project
plan: no service mesh; NATS JetStream over Kafka and Redis Streams;
semantic over exact-match caching; k3s on a single node over a managed
control plane; a read-only, pull-request-only operations agent; Kyverno
over OPA Gatekeeper; the human-review confidence threshold.

## Consequences
Slower to decide, faster to defend. The repository becomes evidence of
reasoning rather than output.
```

**Check:** `git status` shows the new files; running `make` with no target lists the available verbs.

---

# Phase 1 — Containers and the workload

This phase builds the three programs that make up the application and runs them together on one machine. It introduces the core idea of a container and the tools for building and running them.

## Servers, clients and APIs

A server is a computer that runs software and answers requests from other computers, called clients. An API (Application Programming Interface) is a program on a server that answers structured requests over the internet: a client asks for data in a defined format, and the API returns it, usually as JSON. The venue API in this project answers requests such as "list the late-night venues".

## The consistency problem

Software often behaves differently on different machines because they have different versions of programming languages, libraries and settings. Code that works on one computer can fail on another for reasons unrelated to the code itself. This is the problem containers solve.

## Containers

A container packages a program together with everything it needs to run: the language runtime, the libraries, and the system files. The result behaves the same on any machine. Docker is the standard tool for building and running containers. A container is isolated from the host and from other containers, so several can run side by side without interfering.

## Images and Dockerfiles

An image is the frozen, shippable form of a container: a read-only package containing the program and its dependencies. A running image is a container. A Dockerfile is a text file listing the steps to build an image. Images are stored in a registry and pulled wherever they are needed.

## Multi-stage builds and hardening

A multi-stage build uses a temporary stage to install and compile dependencies, then copies only the finished result into a small final image, so build tools are not shipped. Smaller images download faster and expose less to attackers. Beyond size, a hardened container runs as a non-root user (so a break-in lands in a restricted account), uses a read-only filesystem (so the program cannot alter its own files), and drops unnecessary system privileges.

## Health probes

A health probe is a small endpoint the platform checks to ask whether a program is working. Three kinds answer different questions. Liveness asks only whether the process is responding; if not, restart it. Readiness asks whether the program is ready to serve traffic, checking that its dependencies are reachable; if not, hold traffic back but do not restart. Startup covers the initial boot window. Confusing these causes restart loops, for example restarting a program because its database is down.

## Structured logging

A log is a timestamped record of an event. Structured logging writes each log line as machine-readable data (JSON) rather than free text, so it can be searched reliably. A correlation identifier is a random value attached to a request and carried through every service it touches, so the whole journey of one request can be found by searching for that identifier.

## The API service

The venue API, written with FastAPI (a Python framework for building APIs). It provides the three health probes, JSON logging with a correlation identifier, and metrics for monitoring. It serves venue data from a bundled file, or from a database when one is configured.

Create **`apps/api/main.py`**:

```python
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
```

The list of Python libraries the API depends on, pinned to exact versions so builds are reproducible.

Create **`apps/api/requirements.txt`**:

```text
fastapi==0.115.12
uvicorn[standard]==0.34.0
prometheus-fastapi-instrumentator==7.0.2
psycopg[binary]==3.2.6
```

The recipe for the API's image. It uses a multi-stage build and the hardening described above: a non-root user, a read-only filesystem and dropped privileges.

Create **`apps/api/Dockerfile`**:

```text
# Multi-stage build: dependencies compiled in the builder, discarded from
# the final image. Target: under 200 MB, non-root, no build tools shipped.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
# Non-root user; the container refuses to run as root.
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY main.py .
COPY data/ data/
USER 10001
EXPOSE 8000
# Liveness probes /health/live, readiness probes /health/ready.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Automated tests that confirm the API's endpoints behave correctly. These run in the pipeline on every change.

Create **`apps/api/tests/test_api.py`**:

```python
from fastapi.testclient import TestClient

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os

os.environ["VENUES_FILE"] = str(
    Path(__file__).resolve().parents[1] / "data" / "venues.static.json"
)
from main import app  # noqa: E402

client = TestClient(app)


def test_liveness():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness_without_db():
    assert client.get("/health/ready").status_code == 200


def test_static_dataset_loaded():
    r = client.get("/venues", params={"limit": 500})
    assert r.status_code == 200
    assert r.json()["count"] > 1000  # the real snapshot, not the sample


def test_filter_by_vibe():
    body = client.get("/venues", params={"vibe": "late-night"}).json()
    assert body["count"] > 0
    assert all("late-night" in v["tags"] for v in body["venues"])


def test_filter_by_band_and_area():
    body = client.get("/venues", params={"band": "under_5", "area": "lanes"}).json()
    assert all(v["band"] == "under_5" for v in body["venues"])


def test_venue_by_id():
    first = client.get("/venues").json()["venues"][0]
    r = client.get(f"/venues/{first['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == first["name"]


def test_venue_not_found():
    assert client.get("/venues/no-such-id").status_code == 404


def test_feed_ranked():
    venues = client.get("/feed", params={"limit": 10}).json()["venues"]
    assert len(venues) == 10


def test_correlation_id_propagates():
    r = client.get("/venues", headers={"x-correlation-id": "abc123"})
    assert r.headers["x-correlation-id"] == "abc123"
```

The venue dataset (`apps/api/data/venues.static.json`) is a one-time export of about 1,275 records. It is too large to list; any list of objects with `id`, `name`, `area`, `type_label`, `band_label`, `tags`, `rating` and `rating_count` fields works. Place it at that path.

## The inference gateway

The inference gateway is the only program allowed to contact the AI model provider. Concentrating those calls in one service is what makes spending, caching and access controllable later. At this stage it uses a mock so the stack runs with no API key; Phase 5 replaces its internals. The final files are shown in Phase 5; its dependencies and image recipe are below.

Create **`apps/gateway/requirements.txt`**:

```text
fastapi==0.115.12
uvicorn[standard]==0.34.0
prometheus-fastapi-instrumentator==7.0.2
redis==5.2.1
pydantic==2.10.6
anthropic==0.116.0
fastembed==0.4.2
```

The gateway's image recipe. It bakes an embedding model into the image (used in Phase 5) so the running container never downloads anything.

Create **`apps/gateway/Dockerfile`**:

```text
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
# Bake the embedding model into the image so the read-only, egress-locked
# container never downloads anything at runtime.
ENV PYTHONPATH=/install/lib/python3.12/site-packages
ENV FASTEMBED_CACHE_PATH=/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
COPY --from=builder /models /models
ENV FASTEMBED_CACHE_PATH=/models
WORKDIR /app
COPY main.py provider.py semcache.py budget.py ./
COPY prompts/ prompts/
USER 10001
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

## The worker

The worker performs background jobs so that slow work does not block the API. It takes jobs from a queue and processes them at its own pace. Its full behaviour is covered in Phase 4; the final file is shown here.

Create **`apps/worker/main.py`**:

```python
"""
Tamani enrichment worker — consumes venue.enrichment.requested from NATS
JetStream and calls the gateway to classify.

Delivery semantics (Phase 4):
  - at-least-once with idempotency keys, explicit ack after completion
  - retry with exponential backoff, capped delivery count
  - after MAX_DELIVER failed attempts the message moves to the dead
    letter subject for inspection instead of cycling forever
  - malformed payloads go straight to quarantine and are terminated,
    so one poison message cannot take down the consumer pool
  - consumer lag exported as a Prometheus gauge (the autoscaling signal)
"""
import asyncio
import json
import logging
import os
import sys
import time

import httpx
import nats
from nats.js.api import ConsumerConfig, RetentionPolicy, StreamConfig
from prometheus_client import Counter, Gauge, Histogram, start_http_server

SERVICE_NAME = "tamani-worker"
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format=json.dumps({
        "ts": "%(asctime)s", "level": "%(levelname)s",
        "service": SERVICE_NAME, "message": "%(message)s",
    }),
)
log = logging.getLogger(SERVICE_NAME)

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8001")
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "dev-local-key")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PROCESS_DELAY = float(os.getenv("PROCESS_DELAY", "0"))  # chaos/demo hook
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))

STREAM = "VENUE"
SUBJECT_REQUESTED = "venue.enrichment.requested"
SUBJECT_COMPLETED = "venue.enrichment.completed"
SUBJECT_FAILED = "venue.enrichment.failed"
SUBJECT_DLQ = "venue.enrichment.dlq"
SUBJECT_QUARANTINE = "venue.enrichment.quarantine"

MAX_DELIVER = 5
BACKOFF_CAP_SECONDS = 60

PROCESSED = Counter("worker_messages_total", "Messages handled", ["result"])
LATENCY = Histogram("worker_processing_seconds", "Time to process one message")
LAG = Gauge("worker_consumer_pending", "Messages waiting in the consumer")


def backoff_delay(attempt: int) -> float:
    """1s, 2s, 4s, 8s ... capped."""
    return min(2 ** (attempt - 1), BACKOFF_CAP_SECONDS)


def already_done(r, idempotency_key: str) -> bool:
    """The key is written only AFTER successful completion. Claiming it
    up front looks tidier but loses work: a worker killed mid-task would
    leave the claim behind and the redelivery would skip as 'duplicate'.
    The cost is that two concurrent deliveries may both do the work,
    which at-least-once semantics already requires downstream writes to
    tolerate."""
    return bool(r.exists(f"idem:{idempotency_key}"))


async def quarantine(js, msg, reason: str):
    """Poison message: park it with its error, terminate redelivery."""
    await js.publish(SUBJECT_QUARANTINE, json.dumps({
        "reason": reason,
        "raw": msg.data.decode(errors="replace"),
        "stream_seq": msg.metadata.sequence.stream,
    }).encode())
    await msg.term()
    PROCESSED.labels(result="quarantined").inc()
    log.error("quarantined message seq %s: %s", msg.metadata.sequence.stream, reason)


async def dead_letter(js, msg, payload: dict, error: str):
    """Delivery budget exhausted: move to DLQ, stop redelivery."""
    await js.publish(SUBJECT_DLQ, json.dumps({
        "payload": payload,
        "error": error,
        "deliveries": msg.metadata.num_delivered,
        "stream_seq": msg.metadata.sequence.stream,
    }).encode())
    await msg.term()
    PROCESSED.labels(result="dead_lettered").inc()
    log.error("dead-lettered venue %s after %d deliveries: %s",
              payload.get("venue_id"), msg.metadata.num_delivered, error)


async def handle(msg, js, r):
    started = time.monotonic()
    try:
        payload = json.loads(msg.data)
        if "venue_id" not in payload or "description" not in payload:
            raise ValueError("missing venue_id or description")
    except (json.JSONDecodeError, ValueError) as exc:
        await quarantine(js, msg, str(exc))
        return

    idem = payload.get("idempotency_key") or f"venue-{payload['venue_id']}"
    if already_done(r, idem):
        log.info("duplicate delivery for %s, acking without work", idem)
        await msg.ack()
        PROCESSED.labels(result="duplicate").inc()
        return

    try:
        if PROCESS_DELAY:
            await asyncio.sleep(PROCESS_DELAY)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GATEWAY_URL}/v1/classify",
                json={"venue_id": str(payload["venue_id"]),
                      "description": payload["description"]},
                headers={"x-api-key": GATEWAY_KEY},
            )
            resp.raise_for_status()
        await js.publish(SUBJECT_COMPLETED, resp.content)
        r.set(f"idem:{idem}", int(time.time()), ex=86400)  # mark done, then ack
        await msg.ack()  # explicit ack only after the work is complete
        PROCESSED.labels(result="ok").inc()
        LATENCY.observe(time.monotonic() - started)
        log.info("enriched venue %s", payload["venue_id"])
    except Exception as exc:  # noqa: BLE001
        await js.publish(SUBJECT_FAILED, json.dumps(
            {"venue_id": payload.get("venue_id"), "error": str(exc)}
        ).encode())
        if msg.metadata.num_delivered >= MAX_DELIVER:
            await dead_letter(js, msg, payload, str(exc))
        else:
            delay = backoff_delay(msg.metadata.num_delivered)
            PROCESSED.labels(result="retried").inc()
            log.warning("attempt %d for venue %s failed (%s), retry in %.0fs",
                        msg.metadata.num_delivered, payload.get("venue_id"),
                        exc, delay)
            await msg.nak(delay=delay)


async def export_lag(js):
    while True:
        try:
            info = await js.consumer_info(STREAM, "enrichment-workers")
            LAG.set(info.num_pending)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(10)


async def main():
    import redis
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    start_http_server(METRICS_PORT)
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    # Retention by age and size — an unbounded stream eventually fills
    # the volume. 7 days / 256 MiB holds far more than the workload needs.
    config = StreamConfig(
        name=STREAM,
        subjects=["venue.>"],
        retention=RetentionPolicy.LIMITS,
        max_age=7 * 24 * 3600,
        max_bytes=256 * 1024 * 1024,
    )
    try:
        await js.add_stream(config)
    except Exception:  # noqa: BLE001 - exists; apply config changes
        await js.update_stream(config)

    # A durable created by older code as a push consumer will happily let
    # a pull subscription bind to it and then deliver nothing. Detect the
    # type mismatch and recreate rather than debug silence in production.
    try:
        info = await js.consumer_info(STREAM, "enrichment-workers")
        if info.config.deliver_subject:
            log.warning("stale push consumer found, recreating as pull")
            await js.delete_consumer(STREAM, "enrichment-workers")
    except Exception:  # noqa: BLE001 - consumer does not exist yet
        pass

    sub = await js.pull_subscribe(
        SUBJECT_REQUESTED,
        durable="enrichment-workers",
        config=ConsumerConfig(max_deliver=MAX_DELIVER, ack_wait=90),
    )
    asyncio.create_task(export_lag(js))
    log.info("worker consuming %s (max_deliver=%d)", SUBJECT_REQUESTED, MAX_DELIVER)
    while True:
        try:
            msgs = await sub.fetch(1, timeout=30)
        except nats.errors.TimeoutError:
            continue
        for msg in msgs:
            await handle(msg, js, r)


if __name__ == "__main__":
    asyncio.run(main())
```

Create **`apps/worker/requirements.txt`**:

```text
nats-py==2.9.0
httpx==0.28.1
redis==5.2.1
prometheus-client==0.21.1
```

Create **`apps/worker/Dockerfile`**:

```text
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY main.py replay.py ./
USER 10001
CMD ["python", "main.py"]
```

## Docker Compose and the supporting services

Docker Compose starts many containers together from one file. Besides the three programs, the stack includes Redis (a fast in-memory store used for the cache, the job queue and rate limiting), NATS (the message system), Postgres (a database), Prometheus (which collects metrics) and Grafana (which draws dashboards from them).

The Compose file declares every service, how to build or pull it, its ports and its environment, on a shared network where they reach each other by name.

Create **`docker-compose.yml`**:

```yaml
services:
  api:
    build: apps/api
    ports: ["8000:8000"]
    environment:
      STARTUP_GRACE_SECONDS: "0"
    depends_on: [redis]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"]
      interval: 10s
      timeout: 3s
      retries: 5

  gateway:
    build: apps/gateway
    ports: ["8001:8001"]
    environment:
      REDIS_URL: redis://redis:6379/0
      TENANT_KEYS: "dev:dev-local-key,mobile:mobile-local-key,agents:agent-local-key"
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    depends_on: [redis]

  worker:
    build: apps/worker
    environment:
      NATS_URL: nats://nats:4222
      GATEWAY_URL: http://gateway:8001
      GATEWAY_KEY: dev-local-key
      REDIS_URL: redis://redis:6379/0
    depends_on: [nats, gateway, redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  nats:
    image: nats:2.10-alpine
    command: ["-js"]
    ports: ["4222:4222", "8222:8222"]

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: tamani
      POSTGRES_PASSWORD: tamani-local
      POSTGRES_DB: tamani
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  prometheus:
    image: prom/prometheus:v2.53.0
    volumes:
      - ./ops/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:11.1.0
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
    volumes:
      - ./ops/grafana/provisioning:/etc/grafana/provisioning:ro
    ports: ["3000:3000"]

volumes:
  pgdata:
```

Tells the local Prometheus which services to collect metrics from.

Create **`ops/prometheus/prometheus.yml`**:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: tamani-api
    static_configs:
      - targets: ["api:8000"]
  - job_name: tamani-gateway
    static_configs:
      - targets: ["gateway:8001"]
  - job_name: nats
    metrics_path: /metrics
    static_configs:
      - targets: ["nats:8222"]
```

Points the local Grafana at the local Prometheus so dashboards have data.

Create **`ops/grafana/provisioning/datasources/prometheus.yml`**:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```


```bash
make up      # build and start everything
make smoke   # check every service answers
```

**Check:** `make smoke` returns `ok` from the health endpoints and a classification from the gateway; `docker compose ps` shows every service running.

---

# Phase 2 — The Kubernetes platform

This phase runs the services on Kubernetes, with strong separation between environments and rules that limit what any workload can do. It introduces the central technology of the whole project.

## Kubernetes

Docker runs one container; Kubernetes runs many across one or more machines and keeps them running. It is given a written description of the desired state — for example "run two copies of the API, restart them if they fail" — and works continuously to make reality match it. This style is called declarative: the destination is declared, and the system works out the steps.

## Clusters and nodes

A cluster is a set of machines Kubernetes manages as one unit. A node is one machine in the cluster. This project runs a small cluster locally (with minikube) for building and testing, and a real one on a single cloud machine (with k3s) for the live system.

## Pods, deployments and services

A pod is the smallest unit Kubernetes runs, usually a single container. A deployment keeps a chosen number of identical pods running and manages upgrades by replacing them gradually. A service gives a set of pods a stable internal name, such as `tamani-api`, so other programs can reach them even as individual pods come and go.

## Namespaces

A namespace is a partition inside a cluster. This project uses three — for development, staging and production — so the environments cannot interfere with one another and can have different limits and permissions.

## Manifests

A manifest is a YAML file declaring a desired resource, such as a deployment or a service. Applying a manifest tells Kubernetes what should exist; the system then makes it so and keeps it that way.

## Resource quotas and limits

A resource quota caps how much processor time, memory and how many objects a namespace may use. A limit range supplies sensible defaults for containers that do not state their own. Together they stop one workload from starving the others.

## Role-based access control (RBAC)

Role-based access control governs who may do what in the cluster. A role is a set of permitted actions on particular resources; a binding grants a role to a person or program. It exists to enforce least privilege: each user or workload is given only the permissions its job requires, so a mistake or a compromise has limited reach. This project defines a developer role that can read pods and logs but delete nothing, and a deployer role that can update workloads and nothing else.

## Network policy

By default every pod in a cluster can talk to every other pod. A network policy is a firewall between pods that restricts this. The safe pattern is default-deny: block all traffic, then open only the specific paths required. One consequence to remember is that default-deny also blocks DNS — the service that turns names like `redis` into addresses — so DNS must be re-allowed explicitly or nothing can find anything.

## Pod security and admission control

Pod security standards forbid pods from requesting dangerous privileges, such as running as the all-powerful root account. Admission control is a check that inspects every resource entering the cluster and rejects rule-breakers before they run. This project uses Kyverno, an admission controller, to reject images with ambiguous tags, containers without resource limits, and workloads missing required labels.

## The tenancy manifests

Start a local cluster. Calico is a network plugin that actually enforces network policy; minikube's default one silently ignores it.


```bash
minikube start --cni=calico --memory=6g --cpus=4
```

Creates the three namespaces, each set to the restricted pod-security level.

Create **`platform/k8s/tenancy/namespaces.yaml`**:

```yaml
# One namespace per environment. Pod Security admission at restricted:
# no privileged containers, no host namespaces, non-root enforced.
apiVersion: v1
kind: Namespace
metadata:
  name: tamani-dev
  labels:
    env: dev
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: tamani-staging
  labels:
    env: staging
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: tamani-prod
  labels:
    env: prod
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```

Sets a resource quota and default limits for each namespace.

Create **`platform/k8s/tenancy/quotas.yaml`**:

```yaml
# ResourceQuota caps each environment; LimitRange supplies defaults so a
# pod without explicit requests still lands inside the quota.
apiVersion: v1
kind: ResourceQuota
metadata:
  name: env-quota
  namespace: tamani-dev
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 3Gi
    limits.cpu: "4"
    limits.memory: 5Gi
    pods: "20"
    services: "10"
    persistentvolumeclaims: "5"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: env-defaults
  namespace: tamani-dev
spec:
  limits:
    - type: Container
      default:
        cpu: 250m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: env-quota
  namespace: tamani-staging
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 3Gi
    limits.cpu: "4"
    limits.memory: 5Gi
    pods: "20"
    services: "10"
    persistentvolumeclaims: "5"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: env-defaults
  namespace: tamani-staging
spec:
  limits:
    - type: Container
      default:
        cpu: 250m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: env-quota
  namespace: tamani-prod
spec:
  hard:
    requests.cpu: "3"
    requests.memory: 4Gi
    limits.cpu: "6"
    limits.memory: 6Gi
    pods: "30"
    services: "15"
    persistentvolumeclaims: "8"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: env-defaults
  namespace: tamani-prod
spec:
  limits:
    - type: Container
      default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 200m
        memory: 256Mi
```

Defines the developer and deployer roles and binds them.

Create **`platform/k8s/tenancy/rbac.yaml`**:

```yaml
# Two personas per the plan:
#   developer — read pods and logs in one namespace, nothing destructive
#   deployer  — update workloads and nothing else
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer
  namespace: tamani-dev
rules:
  - apiGroups: [""]
    resources: [pods, pods/log, events, services, configmaps]
    verbs: [get, list, watch]
  - apiGroups: [apps]
    resources: [deployments, replicasets]
    verbs: [get, list, watch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: deployer
  namespace: tamani-dev
rules:
  - apiGroups: [apps]
    resources: [deployments]
    verbs: [get, list, watch, update, patch]
  - apiGroups: [""]
    resources: [pods]
    verbs: [get, list, watch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developers
  namespace: tamani-dev
subjects:
  - kind: Group
    name: tamani:developers
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: developer
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deployers
  namespace: tamani-dev
subjects:
  - kind: Group
    name: tamani:deployers
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: deployer
  apiGroup: rbac.authorization.k8s.io
```

## The workload manifests

Blocks all pod traffic by default, then re-allows DNS so name resolution still works.

Create **`platform/k8s/base/netpol-default.yaml`**:

```yaml
# Default deny for ingress and egress, then DNS opened explicitly —
# without the kube-dns rule, every name lookup in the namespace fails.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

Declares the API deployment and service, with resource limits, the three probes, and the security settings.

Create **`platform/k8s/base/api/api.yaml`**:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tamani-api
automountServiceAccountToken: false
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tamani-api
  labels: { app: tamani-api }
spec:
  replicas: 1
  selector:
    matchLabels: { app: tamani-api }
  template:
    metadata:
      labels: { app: tamani-api }
    spec:
      serviceAccountName: tamani-api
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: api
          image: tamani-api
          ports: [{ containerPort: 8000 }]
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { cpu: 500m, memory: 256Mi }
          startupProbe:
            httpGet: { path: /health/startup, port: 8000 }
            failureThreshold: 30
            periodSeconds: 2
          readinessProbe:
            httpGet: { path: /health/ready, port: 8000 }
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /health/live, port: 8000 }
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: tamani-api
  labels: { app: tamani-api }
spec:
  selector: { app: tamani-api }
  ports: [{ port: 80, targetPort: 8000 }]
---
# The API serves read traffic from its bundled snapshot: ingress from
# anywhere in-namespace (the edge arrives with ingress-nginx later),
# egress nothing beyond DNS.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tamani-api
spec:
  podSelector:
    matchLabels: { app: tamani-api }
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector: {}
      ports:
        - port: 8000
```

A pod disruption budget, ensuring at least one API pod always survives a voluntary disruption such as a drain (explained further in Phase 9; included now).

Create **`platform/k8s/base/api/pdb.yaml`**:

```yaml
# At least one API replica must survive any voluntary disruption
# (drain, eviction, chaos experiment).
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: tamani-api
spec:
  minAvailable: 1
  selector:
    matchLabels: { app: tamani-api }
```

The gateway deployment and service, plus a network policy allowing only the worker to call it and only its own outbound paths.

Create **`platform/k8s/base/gateway/gateway.yaml`**:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tamani-gateway
automountServiceAccountToken: false
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tamani-gateway
  labels: { app: tamani-gateway }
spec:
  replicas: 1
  selector:
    matchLabels: { app: tamani-gateway }
  template:
    metadata:
      labels: { app: tamani-gateway }
    spec:
      serviceAccountName: tamani-gateway
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: gateway
          image: tamani-gateway
          ports: [{ containerPort: 8001 }]
          env:
            - name: REDIS_URL
              value: redis://redis:6379/0
            - name: TENANT_KEYS
              value: "dev:dev-local-key" # ESO-provided secret from Phase 8
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { cpu: 500m, memory: 256Mi }
          readinessProbe:
            httpGet: { path: /health/ready, port: 8001 }
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /health/live, port: 8001 }
            periodSeconds: 10
          # Root stays read-only; the embedding runtime needs one scratch dir.
          volumeMounts:
            - { name: tmp, mountPath: /tmp }
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: tamani-gateway
  labels: { app: tamani-gateway }
spec:
  selector: { app: tamani-gateway }
  ports: [{ port: 80, targetPort: 8001 }]
---
# Only the worker may call the gateway. Egress: redis, plus HTTPS out to
# the LLM provider — the single external call path the platform allows,
# and only from this one workload.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tamani-gateway
spec:
  podSelector:
    matchLabels: { app: tamani-gateway }
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app: tamani-worker }
      ports:
        - port: 8001
  egress:
    - to:
        - podSelector:
            matchLabels: { app: redis }
      ports:
        - port: 6379
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except: [10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16]
      ports:
        - port: 443
```

Create **`platform/k8s/base/worker/worker.yaml`**:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tamani-worker
automountServiceAccountToken: false
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tamani-worker
  labels: { app: tamani-worker }
spec:
  replicas: 1
  selector:
    matchLabels: { app: tamani-worker }
  template:
    metadata:
      labels: { app: tamani-worker }
    spec:
      serviceAccountName: tamani-worker
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: worker
          image: tamani-worker
          env:
            - name: NATS_URL
              value: nats://nats:4222
            - name: GATEWAY_URL
              value: http://tamani-gateway
            - name: GATEWAY_KEY
              value: dev-local-key
            - name: REDIS_URL
              value: redis://redis:6379/0
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { cpu: 500m, memory: 256Mi }
---
# No ingress at all; egress only to the things it genuinely calls.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tamani-worker
spec:
  podSelector:
    matchLabels: { app: tamani-worker }
  policyTypes: [Ingress, Egress]
  egress:
    - to:
        - podSelector:
            matchLabels: { app: tamani-gateway }
      ports: [{ port: 8001 }]
    - to:
        - podSelector:
            matchLabels: { app: nats }
      ports: [{ port: 4222 }]
    - to:
        - podSelector:
            matchLabels: { app: redis }
      ports: [{ port: 6379 }]
```

Create **`platform/k8s/base/redis/redis.yaml`**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  labels: { app: redis }
spec:
  replicas: 1
  selector:
    matchLabels: { app: redis }
  template:
    metadata:
      labels: { app: redis }
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: redis
          image: redis:7-alpine
          ports: [{ containerPort: 6379 }]
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits: { cpu: 250m, memory: 256Mi }
          volumeMounts:
            - { name: data, mountPath: /data }
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector: { app: redis }
  ports: [{ port: 6379 }]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: redis
spec:
  podSelector:
    matchLabels: { app: redis }
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app: tamani-gateway }
        - podSelector:
            matchLabels: { app: tamani-worker }
      ports:
        - port: 6379
```

Create **`platform/k8s/base/nats/nats.yaml`**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nats
  labels: { app: nats }
spec:
  replicas: 1
  selector:
    matchLabels: { app: nats }
  template:
    metadata:
      labels: { app: nats }
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: nats
          image: nats:2.10-alpine
          args: ["-js", "--store_dir", "/data"]
          ports:
            - { containerPort: 4222, name: client }
            - { containerPort: 8222, name: monitor }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits: { cpu: 250m, memory: 256Mi }
          volumeMounts:
            - { name: data, mountPath: /data }
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: nats
spec:
  selector: { app: nats }
  ports:
    - { port: 4222, name: client }
    - { port: 8222, name: monitor }
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nats
spec:
  podSelector:
    matchLabels: { app: nats }
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app: tamani-worker }
        - podSelector:
            matchLabels: { app: tamani-api }
      ports:
        - port: 4222
```

A kustomization lists the manifests that form one bundle. This base is shared by all environments.

Create **`platform/k8s/base/kustomization.yaml`**:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - netpol-default.yaml
  - api/api.yaml
  - api/pdb.yaml
  - gateway/gateway.yaml
  - worker/worker.yaml
  - redis/redis.yaml
  - nats/nats.yaml
```

An overlay adjusts the base for one environment. The dev overlay sets development image tags.

Create **`platform/k8s/overlays/dev/kustomization.yaml`**:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: tamani-dev
resources:
  - ../../base
images:
  - name: tamani-api
    newTag: dev
  - name: tamani-gateway
    newTag: dev
  - name: tamani-worker
    newTag: dev
```

Create **`platform/k8s/overlays/staging/kustomization.yaml`**:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: tamani-staging
resources:
  - ../../base
images:
  - name: tamani-api
    newTag: staging
  - name: tamani-gateway
    newTag: staging
  - name: tamani-worker
    newTag: staging
```

The production overlay pins images to exact versions and sets production replica counts and settings.

Create **`platform/k8s/overlays/prod/kustomization.yaml`**:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: tamani-prod
resources:
  - ../../base
# Prod pins image digests by commit sha; promotion is a PR that updates
# these tags (Argo CD Image Updater automates dev later, per the plan).
images:
  - name: tamani-api
    newName: ghcr.io/maicymxtim/tamani-api
    newTag: 0e128d294efeab83c390bd0748394f91984fe7f9
  - name: tamani-gateway
    newName: ghcr.io/maicymxtim/tamani-gateway
    newTag: 0e128d294efeab83c390bd0748394f91984fe7f9
  - name: tamani-worker
    newName: ghcr.io/maicymxtim/tamani-worker
    newTag: 0e128d294efeab83c390bd0748394f91984fe7f9
# maxSurge 0: on a one-node cluster a deploy surge doubles memory and
# took the node down (postmortem 2026-07-23). Replace, don't surge.
patches:
  - target:
      kind: Deployment
    patch: |
      - op: add
        path: /spec/strategy
        value:
          type: RollingUpdate
          rollingUpdate:
            maxSurge: 0
            maxUnavailable: 1
  - target:
      kind: Deployment
      name: tamani-api
    patch: |
      - op: replace
        path: /spec/replicas
        value: 2
  # The real gateway needs the provider key (cluster secret, never in Git)
  # and more memory for the embedding model.
  - target:
      kind: Deployment
      name: tamani-gateway
    patch: |
      - op: replace
        path: /spec/replicas
        value: 1
      - op: add
        path: /spec/template/spec/containers/0/env/-
        value:
          name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: anthropic
              key: api-key
      - op: replace
        path: /spec/template/spec/containers/0/resources
        value:
          requests: { cpu: 100m, memory: 384Mi }
          limits: { cpu: "1", memory: 768Mi }
```

The Kyverno admission policies: forbid ambiguous image tags, require resource limits, require labels.

Create **`platform/policies/baseline.yaml`**:

```yaml
# Admission policy: what the cluster refuses regardless of who asks.
# Enforce mode in the tamani namespaces; image signature verification
# joins these in Phase 8.
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-pinned-tag
      match:
        any:
          - resources:
              kinds: [Pod]
              namespaceSelector:
                matchExpressions:
                  - { key: env, operator: In, values: [dev, staging, prod] }
      validate:
        message: "Images must use a pinned tag, not latest or none."
        pattern:
          spec:
            containers:
              - image: "!*:latest & *:*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-limits
      match:
        any:
          - resources:
              kinds: [Pod]
              namespaceSelector:
                matchExpressions:
                  - { key: env, operator: In, values: [dev, staging, prod] }
      validate:
        message: "Every container needs cpu and memory limits."
        pattern:
          spec:
            containers:
              - resources:
                  limits:
                    cpu: "?*"
                    memory: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-app-label
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-app-label
      match:
        any:
          - resources:
              kinds: [Deployment]
              namespaceSelector:
                matchExpressions:
                  - { key: env, operator: In, values: [dev, staging, prod] }
      validate:
        message: "Deployments need an app label for policy and cost attribution."
        pattern:
          metadata:
            labels:
              app: "?*"
```

Apply the tenancy, build the images into the cluster, deploy the dev environment, and install the admission controller and its policies. (`kubectl` is the command-line tool for a cluster; `helm` installs third-party components.)


```bash
kubectl apply -f platform/k8s/tenancy/
eval $(minikube docker-env)
docker build -t tamani-api:dev apps/api
docker build -t tamani-gateway:dev apps/gateway
docker build -t tamani-worker:dev apps/worker
kubectl apply -k platform/k8s/overlays/dev
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno -n kyverno --create-namespace --wait
kubectl apply -f platform/policies/baseline.yaml
```

**Check:** Asking the cluster whether the developer role may delete deployments returns `no`; a pod using an ambiguous `latest` tag is refused at admission; the API pod cannot reach the gateway while the worker can.

---

# Phase 4 — The event backbone

This phase makes the movement of background work reliable, so no job is lost even when programs crash. The worker built in Phase 1 already contains this behaviour; the concepts explain why it is written that way.

## Synchronous and asynchronous work

Synchronous work happens while the caller waits for an answer. Asynchronous work is handed off to be done later, freeing the caller to continue. Work that does not need an immediate answer, such as re-classifying many venues, should be asynchronous so it does not block fast requests.

## Message queues and streams

A message queue moves work between programs. A producer places a message on the queue; a consumer takes it off and processes it. A stream is a durable, ordered log of messages saved to disk, so messages survive restarts. This project uses NATS JetStream. A subject is a message's address, and a consumer group lets several workers share a stream with each message going to exactly one of them.

## Delivery guarantees and idempotency

At-least-once delivery means a message is delivered one or more times — occasionally more than once. To make that safe, every consumer must be idempotent: processing the same message twice has no additional effect. This is achieved with an idempotency key recorded after the work succeeds, so a repeat is recognised and skipped.

## Acknowledgement and redelivery

A worker acknowledges a message only after completing the work. If it crashes before acknowledging, the message is redelivered to another worker rather than lost. Acknowledging on receipt instead of on completion silently loses work whenever a worker restarts mid-task.

## Dead letter queues and poison messages

A message that keeps failing is retried with growing delays (exponential backoff) and, after a limit, moved to a dead letter queue for inspection rather than retried forever. A poison message is a malformed message that crashes any consumer that reads it; it is quarantined immediately so it cannot take down the whole worker pool.

## The replay tool and decision record

Re-sends messages from a chosen point in the stream, used to reprocess history after a change to how work is done.

Create **`apps/worker/replay.py`**:

```python
"""
Replay venue.enrichment.requested messages from a chosen stream sequence.

Used for backfill and for reprocessing after a classifier or prompt
change: republishes each historical request with a replay-scoped
idempotency key so workers treat it as fresh work.

  python replay.py --from-seq 1 [--dry-run]
"""
import argparse
import asyncio
import json
import os
import time

import nats
from nats.js.api import ConsumerConfig, DeliverPolicy

STREAM = "VENUE"
SUBJECT_REQUESTED = "venue.enrichment.requested"


async def main(from_seq: int, dry_run: bool):
    nc = await nats.connect(os.getenv("NATS_URL", "nats://localhost:4222"))
    js = nc.jetstream()
    replay_tag = int(time.time())

    sub = await js.subscribe(
        SUBJECT_REQUESTED,
        ordered_consumer=True,
        config=ConsumerConfig(
            deliver_policy=DeliverPolicy.BY_START_SEQUENCE,
            opt_start_seq=from_seq,
        ),
    )
    replayed = 0
    while True:
        try:
            msg = await sub.next_msg(timeout=3)
        except nats.errors.TimeoutError:
            break
        seq = msg.metadata.sequence.stream
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            print(f"seq {seq}: skipped (not json)")
            continue
        payload["idempotency_key"] = f"replay-{replay_tag}-{seq}"
        if not dry_run:
            await js.publish(SUBJECT_REQUESTED, json.dumps(payload).encode())
        replayed += 1
        print(f"seq {seq}: venue {payload.get('venue_id')}"
              f"{' (dry run)' if dry_run else ' republished'}")
    print(f"replayed {replayed} messages from sequence {from_seq}")
    await nc.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--from-seq", type=int, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.from_seq, args.dry_run))
```

The decision record explaining why NATS was chosen over the alternatives, weighing durability and features against operational weight.

Create **`docs/adr/0002-nats-jetstream-over-kafka-and-redis-streams.md`**:

```markdown
# ADR 0002: NATS JetStream over Kafka and Redis Streams

## Status
Accepted

## Context
The platform needs an event backbone for enrichment jobs and agent
triggers: durable delivery, consumer groups so worker replicas share a
stream, replay for backfill, and dead-lettering. Peak volume is a few
thousand messages a day — the 1,275-venue catalogue reclassified end to
end is one burst of ~1,300 messages. The cluster is a single 2 GB node.

## Options
**Kafka.** The industry default, unmatched ecosystem and throughput.
But a JVM broker plus controller quorum wants gigabytes of memory the
node does not have, partitions must be sized upfront, and its strengths
(horizontal scale, log compaction, exactly-once transactions) address
problems this workload will never have.

**Redis Streams.** Already running Redis for cache and rate limiting, so
zero new components. Consumer groups and replay exist. But persistence
is best-effort (AOF tuning), there is no subject hierarchy so routing
becomes key naming convention, no per-message redelivery budget, and
using the cache as the system of record couples two failure domains.

**NATS JetStream.** A single ~15 MB binary with file-backed streams,
subject hierarchies (`venue.enrichment.*` addressable separately),
durable consumer groups, per-consumer max-delivery with backoff, replay
from any sequence, and retention by age and size. Weaknesses: smaller
ecosystem, no compaction, and at-least-once (not exactly-once) semantics.

## Decision
NATS JetStream. At-least-once is accepted and made safe with idempotency
keys on every consumer. The lightest option that satisfies every stated
requirement wins; operational weight is the scarcest resource here.

## Consequences
Idempotency is mandatory in every consumer, forever. Replay and DLQ
behaviour is proven by test (see Phase 4 demos). If requirements grow to
multi-datacentre replication or compacted change logs, revisit Kafka —
the publish/consume seam keeps that swap contained.
```

**Check:** Invalid data is quarantined without crashing the workers; a message that always fails moves to the dead-letter subject after five attempts with visible backoff; a worker killed mid-message has its work completed by another.

---

# Phase 5 — The inference gateway

This phase connects a real AI model and surrounds it with cost control, caching and safety. It replaces the gateway skeleton from Phase 1.

## Language models and inference

A language model is a trained program that produces text in response to a prompt. Inference means obtaining a result from such a model. Each inference call costs money, charged per unit of text (tokens), so calls must be controlled and measured.

## The single-gateway pattern

Routing every model call through one service means the provider key exists in only one place, and spending, caching and access rules are enforced centrally rather than scattered across the system. No other program holds the key or calls the provider directly.

## Structured output

Structured output constrains the model to return data matching a fixed schema, so the response is valid by construction and does not need fragile parsing. This project requires the classifier to return a defined set of vibe tags and a confidence value.

## Embeddings and semantic caching

An embedding is a list of numbers representing the meaning of a piece of text; similar meanings produce similar numbers. A semantic cache uses embeddings to recognise that a new request is close enough in meaning to a previous one and returns the stored answer without calling the provider. The similarity threshold is tuned against real data, because too loose a threshold serves confidently wrong answers.

## Token budgets and rate limiting

A token budget is a per-caller limit on how much text may be spent, enforced per minute and per day. A caller that exceeds its budget is refused with a retry-after signal. This is enforcement, not merely observation: an over-budget caller is throttled automatically.

## Circuit breakers and fallback

A circuit breaker stops calling a dependency that is repeatedly failing and falls back to a safe alternative, so a provider outage degrades the service instead of breaking it. This gateway falls back to a deterministic local classifier, and never caches those fallback results.

## Prompt versioning and cost ledgers

The prompt is treated as a versioned artifact stored in the repository, and the version is recorded alongside every classification, so any result can be traced to the exact prompt that produced it. A cost ledger records every request's model, tokens and cost, making spend measurable.

## The gateway files

Provide the provider key locally. The `.env` file is ignored by Git, so the key never enters version control.


```bash
echo 'ANTHROPIC_API_KEY=sk-ant-YOUR-KEY' > .env
```

The classification prompt. Each prompt is a separate, versioned file.

Create **`apps/gateway/prompts/classify_v1.md`**:

```markdown
You classify restaurant and bar venues for a discovery app in Brighton, UK.

Given a venue description, assign the vibe tags that genuinely fit. Tags:

- special-occasion: upscale, celebratory, somewhere you book for a birthday
- sit-down: table service, a proper meal
- drinks: good for alcoholic drinks, bar-like
- groups: suits parties of 4 or more
- late-night: open and lively late in the evening
- coffee: coffee is a core part of the offer
- quick: fast service, counter service, grab-and-go
- work-friendly: laptop-friendly, daytime, wifi culture
- brunch: daytime breakfast/brunch offer
- solo-friendly: comfortable to visit alone

Rules: assign 1 to 4 tags. Only tag what the description supports. Set
confidence between 0 and 1 reflecting how well the description supports
your tags: short or vague descriptions mean low confidence.
```

The provider layer: real model calls with structured output, pricing, a circuit breaker, and the deterministic mock fallback.

Create **`apps/gateway/provider.py`**:

```python
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


def complete(prompt: str, max_tokens: int = 1500) -> dict:
    """Generic completion for agent reasoning. No cache, budgeted like
    everything else, cost attributed by purpose in the ledger."""
    import anthropic

    if breaker.open:
        raise CircuitOpen("anthropic circuit open")
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except (anthropic.APIConnectionError, anthropic.RateLimitError,
            anthropic.InternalServerError):
        breaker.record_failure()
        raise
    if response.stop_reason == "refusal":
        breaker.record_success()
        raise ValueError("provider refused the request")
    breaker.record_success()
    text = next(b.text for b in response.content if b.type == "text")
    return {
        "text": text,
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
```

The semantic cache: it computes embeddings locally and compares them by similarity, so caching adds no provider cost.

Create **`apps/gateway/semcache.py`**:

```python
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
```

The per-tenant token budgets, enforced per minute and per day.

Create **`apps/gateway/budget.py`**:

```python
"""
Per-tenant token budgets, enforced per minute and per day. Exhausted
budgets return 429 with a retry-after, which is enforcement rather than
observation: an over-quota tenant is throttled automatically.
"""
import os
import time

# "tenant:per_minute:per_day,..."
_DEFAULT = "dev:20000:400000,mobile:20000:400000"


def limits() -> dict[str, tuple[int, int]]:
    out = {}
    for part in os.getenv("TENANT_TOKEN_LIMITS", _DEFAULT).split(","):
        tenant, per_min, per_day = part.strip().split(":")
        out[tenant] = (int(per_min), int(per_day))
    return out


def check(r, tenant: str) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    per_min, per_day = limits().get(tenant, (20000, 400000))
    now = int(time.time())
    minute_used = int(r.get(f"quota:{tenant}:m:{now // 60}") or 0)
    day_used = int(r.get(f"quota:{tenant}:d:{now // 86400}") or 0)
    if minute_used >= per_min:
        return False, 60 - now % 60
    if day_used >= per_day:
        return False, 86400 - now % 86400
    return True, 0


def consume(r, tenant: str, tokens: int):
    now = int(time.time())
    minute_key = f"quota:{tenant}:m:{now // 60}"
    day_key = f"quota:{tenant}:d:{now // 86400}"
    pipe = r.pipeline()
    pipe.incrby(minute_key, tokens)
    pipe.expire(minute_key, 120)
    pipe.incrby(day_key, tokens)
    pipe.expire(day_key, 90000)
    pipe.execute()
```

The request path that ties it together: authenticate, check the budget, look in the cache, call the provider on a miss, store the result, record the cost.

Create **`apps/gateway/main.py`**:

```python
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
SPEND = Counter("gateway_spend_usd_total", "Provider spend in USD", ["purpose"])
SAVED = Counter("gateway_saved_usd_total", "Spend avoided by the cache")
TOKENS = Counter("gateway_tokens_total", "Provider tokens", ["purpose", "direction"])


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
    SPEND.labels("classification").inc(result["cost_usd"])
    SAVED.inc(saved)
    TOKENS.labels("classification", "in").inc(result["input_tokens"])
    TOKENS.labels("classification", "out").inc(result["output_tokens"])
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


class CompleteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=30000)
    purpose: str = Field(default="agent-reasoning", max_length=40)
    max_tokens: int = Field(default=1500, le=3000)


@app.post("/v1/complete")
def complete(req: CompleteRequest, tenant_id: str = Depends(tenant)):
    """Agent reasoning goes through the same door as everything else:
    tenant budgets, ledger attribution by purpose, no provider key in
    any agent."""
    r = _redis()
    allowed, retry_after = budget.check(r, tenant_id)
    if not allowed:
        raise HTTPException(status_code=429, detail="token budget exhausted",
                            headers={"retry-after": str(retry_after)})
    try:
        result = provider.complete(req.prompt, req.max_tokens)
    except Exception as exc:  # noqa: BLE001
        log.error("completion failed: %s", exc)
        raise HTTPException(status_code=502, detail="provider unavailable")
    budget.consume(r, tenant_id, result["input_tokens"] + result["output_tokens"])
    SPEND.labels(req.purpose).inc(result["cost_usd"])
    TOKENS.labels(req.purpose, "in").inc(result["input_tokens"])
    TOKENS.labels(req.purpose, "out").inc(result["output_tokens"])
    r.xadd("cost:ledger", {
        "tenant": tenant_id, "model": result["model"], "purpose": req.purpose,
        "cached": 0, "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "cost_usd": f"{result['cost_usd']:.8f}", "saved_usd": "0",
    })
    return result


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
```


```bash
make up
curl -s -X POST http://localhost:8001/v1/classify \
  -H 'x-api-key: dev-local-key' -H 'content-type: application/json' \
  -d '{"venue_id":"t1","description":"late night cocktail bar"}'
```

**Check:** The first classification calls the provider and reports a real cost; a near-duplicate description returns a cached result at zero cost; the `/v1/costs` endpoint reports spend and cache savings.

---

# Phase 6 — Evaluation and governed agents

This phase measures the AI's accuracy against human judgement, guards it in the pipeline, and builds two agents kept safe by a governance layer.

## AI agents

An AI agent is a program that uses a model to decide which actions to take, in a loop, to accomplish a task. Agents are powerful but risky: without limits they can loop, overspend, or take unintended actions. Making them safe to run unattended is the real engineering.

## Evaluation, golden sets, precision and recall

A golden set is a collection of examples judged by a human, used as the standard of correct answers. Evaluation runs the model over the golden set and scores it. Precision is the share of the model's assigned tags that were correct; recall is the share of the correct tags that the model found. Together they describe accuracy for a task where several tags can apply.

## Regression gates

A regression gate is an automated check that blocks a change if it makes a measured result worse. Here, any change to the classifier is scored against the golden set, and the pipeline fails if accuracy drops beyond a tolerance, so an apparently reasonable prompt change cannot silently degrade quality.

## Agent governance

The governance layer is a runtime that surrounds an agent and enforces limits. A capability manifest lists the only tools the agent may use; anything outside it is refused. Budgets cap the tokens, wall-clock time and number of actions per run. Loop detection halts an agent repeating the same action, the most common runaway failure. A dry-run mode records every action without performing side effects, for safe validation. Every action is traced for inspection.

## Least privilege for agents

The operations agent is additionally restricted at the infrastructure level: its cluster identity may only read (get, list and watch), never change anything. It produces a diagnosis and opens a pull request for a human to approve, rather than acting directly.

## Building the golden set

Generates a browser page for labelling venues. It is run once, the venues are labelled by hand, and the result is exported to `evals/golden_set.jsonl`.

Create **`evals/make_labeler.py`**:

```python
"""Generate tools/labeler.html — the golden-set labelling page.

Samples venues, embeds them with their current tags preselected (you
correct rather than start from scratch), and produces a single HTML file
with no server dependency. Progress persists in the browser; Export
downloads golden_set.json.

    python3 evals/make_labeler.py
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
venues = json.load(open(ROOT / "apps/api/data/venues.static.json"))

# AI suggestions for the previously-untagged venues, if the backfill ran
suggestions = {}
backfill = ROOT / "evals/backfill_results.json"
if backfill.exists():
    for r in json.load(open(backfill)):
        suggestions[r["venue_id"]] = r["vibes"]

untagged = [v for v in venues if not v.get("tags")]
tagged = [v for v in venues if v.get("tags")]
random.seed(42)
sample = random.sample(tagged, 110) + untagged

items = []
for v in sample:
    items.append({
        "id": v["id"],
        "name": v["name"],
        "meta": " · ".join(str(x) for x in [
            v.get("type_label"), v.get("area"), v.get("band_label"),
            f"{v.get('rating')}★ ({v.get('rating_count')})"] if x),
        "maps": v.get("maps_uri") or "",
        "pre": v.get("tags") or suggestions.get(v["id"], []),
    })
random.shuffle(items)

TAGS = ["special-occasion", "sit-down", "drinks", "groups", "late-night",
        "coffee", "quick", "work-friendly", "brunch", "solo-friendly"]

html = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tamani golden set labeller</title>
<style>
:root { --bg:#101418; --card:#1a2129; --text:#e8edf2; --dim:#8b98a5;
        --on:#2f6f4f; --onb:#57c78e; --accent:#d78a3d; }
@media (prefers-color-scheme: light) {
  :root { --bg:#f4f2ee; --card:#ffffff; --text:#22282e; --dim:#6b7680;
          --on:#d9efe3; --onb:#1e7a4d; }
}
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--text);
       font:16px/1.5 -apple-system, system-ui, sans-serif;
       display:flex; justify-content:center; padding:24px 12px; }
main { width:100%; max-width:560px; }
.progress { height:6px; background:var(--card); border-radius:3px; margin-bottom:16px; }
.progress div { height:100%; background:var(--accent); border-radius:3px; }
.card { background:var(--card); border-radius:14px; padding:22px; }
h1 { font-size:1.35rem; margin-bottom:4px; }
.meta { color:var(--dim); font-size:.9rem; margin-bottom:6px; }
.meta a { color:var(--accent); }
.count { color:var(--dim); font-size:.85rem; margin-bottom:14px; }
.tags { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:14px 0 20px; }
button.tag { padding:12px 10px; border-radius:10px; border:2px solid transparent;
  background:var(--bg); color:var(--text); font-size:.95rem; cursor:pointer; text-align:left; }
button.tag.on { background:var(--on); border-color:var(--onb); font-weight:600; }
button.tag small { color:var(--dim); }
.nav { display:flex; gap:10px; }
.nav button { flex:1; padding:12px; border-radius:10px; border:0; cursor:pointer;
  font-size:1rem; background:var(--bg); color:var(--text); }
.nav button.primary { background:var(--accent); color:#171310; font-weight:700; }
.footer { margin-top:14px; display:flex; justify-content:space-between;
  color:var(--dim); font-size:.85rem; }
.footer button { background:none; border:0; color:var(--accent); cursor:pointer; font-size:.85rem; }
kbd { background:var(--card); padding:1px 5px; border-radius:4px; border:1px solid var(--dim); }
</style>
<main>
  <div class="progress"><div id="bar"></div></div>
  <div class="card">
    <h1 id="name"></h1>
    <div class="meta" id="meta"></div>
    <div class="count" id="count"></div>
    <div class="tags" id="tags"></div>
    <div class="nav">
      <button onclick="move(-1)">&larr; Back</button>
      <button onclick="skip()" title="don't know this venue">Skip</button>
      <button class="primary" onclick="move(1)">Save &amp; next &rarr;</button>
    </div>
    <div class="footer">
      <span>Keys: <kbd>1</kbd>–<kbd>0</kbd> toggle · <kbd>&crarr;</kbd> next</span>
      <button onclick="exportSet()">Export golden_set.json</button>
    </div>
  </div>
</main>
<script>
const TAGS = __TAGS__;
const ITEMS = __ITEMS__;
let labels = JSON.parse(localStorage.getItem("golden") || "{}");
let i = Number(localStorage.getItem("golden_i") || 0);

function current() { return ITEMS[i]; }
function selected() {
  const v = current();
  if (labels[v.id]) return new Set(labels[v.id].tags);
  return new Set(v.pre);
}
function render() {
  const v = current(); const sel = selected();
  document.getElementById("name").textContent = v.name;
  document.getElementById("meta").innerHTML =
    v.meta + (v.maps ? ' · <a href="' + v.maps + '" target="_blank">map</a>' : "");
  const done = Object.keys(labels).length;
  document.getElementById("count").textContent =
    "Venue " + (i+1) + " of " + ITEMS.length + " — " + done + " labelled";
  document.getElementById("bar").style.width = (100 * done / ITEMS.length) + "%";
  const box = document.getElementById("tags"); box.innerHTML = "";
  TAGS.forEach((t, n) => {
    const b = document.createElement("button");
    b.className = "tag" + (sel.has(t) ? " on" : "");
    b.innerHTML = "<small>" + ((n+1) % 10) + "</small> " + t;
    b.onclick = () => { toggle(t); };
    box.appendChild(b);
  });
}
function toggle(t) {
  const v = current(); const sel = selected();
  sel.has(t) ? sel.delete(t) : sel.add(t);
  labels[v.id] = { tags: [...sel], skipped: false };
  persist(); render();
}
function save() {
  const v = current();
  if (!labels[v.id]) labels[v.id] = { tags: [...selected()], skipped: false };
}
function skip() {
  labels[current().id] = { tags: [], skipped: true };
  persist(); move(1, true);
}
function move(d, noSave) {
  if (d > 0 && !noSave) save();
  i = Math.min(Math.max(i + d, 0), ITEMS.length - 1);
  persist(); render();
  if (d > 0 && Object.keys(labels).length >= ITEMS.length) exportSet();
}
function persist() {
  localStorage.setItem("golden", JSON.stringify(labels));
  localStorage.setItem("golden_i", i);
}
function exportSet() {
  const out = ITEMS.filter(v => labels[v.id] && !labels[v.id].skipped)
    .map(v => ({ venue_id: v.id, name: v.name,
                 description: v.name + ". " + v.meta, tags: labels[v.id].tags }));
  const blob = new Blob([out.map(o => JSON.stringify(o)).join("\\n")],
                        { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "golden_set.jsonl";
  a.click();
}
document.addEventListener("keydown", e => {
  if (e.key === "Enter") move(1);
  else if (e.key === "ArrowLeft") move(-1);
  else if (e.key === "ArrowRight") move(1);
  else if (/^[0-9]$/.test(e.key)) toggle(TAGS[(Number(e.key) + 9) % 10]);
});
render();
</script>
"""

out = ROOT / "tools/labeler.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html.replace("__TAGS__", json.dumps(TAGS))
                   .replace("__ITEMS__", json.dumps(items)))
print(f"wrote {out} with {len(items)} venues "
      f"({len(untagged)} previously untagged, AI-prefilled)")
```


```bash
python3 evals/make_labeler.py
open tools/labeler.html          # label the venues, then Export
mv ~/Downloads/golden_set.jsonl evals/golden_set.jsonl
```

## The evaluation harness and gate

Sends every golden-set venue through the classifier and reports precision and recall per tag.

Create **`evals/run_eval.py`**:

```python
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
```

Compares the latest evaluation to a stored baseline and fails if accuracy regresses beyond tolerance.

Create **`evals/check_gate.py`**:

```python
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
latest_file = ROOT / "results" / "latest.json"
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
```

The pipeline that runs the evaluation automatically whenever the classifier changes.

Create **`.github/workflows/eval.yml`**:

```yaml
name: eval-gate

# The accuracy gate: any change to the classifier's prompt or code is
# scored against the golden set, and a regression beyond tolerance fails
# the workflow. Costs ~$0.60 per run, so it only triggers on relevant paths.
on:
  push:
    branches: [main]
    paths:
      - "apps/gateway/**"
      - "evals/golden_set.jsonl"
      - "evals/run_eval.py"
      - "evals/check_gate.py"
      - "evals/baseline.json"

jobs:
  eval:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: install gateway deps
        run: pip install -q -r apps/gateway/requirements.txt
      - name: start gateway
        working-directory: apps/gateway
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          REDIS_URL: redis://localhost:6379/0
        run: |
          nohup uvicorn main:app --port 8001 &
          for i in $(seq 1 30); do
            curl -fsS http://localhost:8001/health/ready && break || sleep 2
          done
      - name: run eval
        run: python3 evals/run_eval.py
      - name: regression gate
        run: python3 evals/check_gate.py
```

After the first successful evaluation, save its scores to `evals/baseline.json` as the baseline the gate compares against.

## The governance runtime and agents

The shared governance runtime enforcing the manifest, budgets, loop detection, dry-run and tracing. Both agents import it.

Create **`apps/agents/governance.py`**:

```python
"""
The governance runtime. Building an agent is a weekend; this is what
makes autonomous execution safe enough to run unattended:

  - capability manifest: a tool not declared in the manifest cannot be
    called, no matter what the agent decides
  - bounded execution: token, wall-clock and tool-call budgets, with the
    run terminated and marked incomplete on breach
  - loop detection: identical tool call repeated beyond the limit halts
    the run (the most common and most expensive runaway failure)
  - dry-run: every call is recorded; side-effectful tools are simulated
  - traceability: every call emitted as a span with args, latency,
    outcome and token cost
"""
import json
import time


class GovernanceViolation(Exception):
    pass


class Governor:
    def __init__(self, manifest: dict, tools: dict, dry_run: bool = False):
        self.manifest = manifest
        self.tools = tools  # name -> (fn, has_side_effects)
        self.dry_run = dry_run
        self.started = time.monotonic()
        self.tokens_used = 0
        self.call_count = 0
        self.recent_calls: list[str] = []
        self.spans: list[dict] = []
        self.status = "running"

    def _check(self, tool: str, args: dict):
        b = self.manifest["budgets"]
        if tool not in self.manifest["allowed_tools"]:
            raise GovernanceViolation(f"tool '{tool}' is not in the capability manifest")
        if time.monotonic() - self.started > b["max_wall_clock_seconds"]:
            raise GovernanceViolation("wall clock budget exhausted")
        if self.call_count >= b["max_tool_calls"]:
            raise GovernanceViolation("tool call budget exhausted")
        if self.tokens_used >= b["max_tokens_per_run"]:
            raise GovernanceViolation("token budget exhausted")
        fingerprint = tool + ":" + json.dumps(args, sort_keys=True)
        limit = self.manifest["loop_detection"]["identical_call_limit"]
        if self.recent_calls.count(fingerprint) >= limit:
            raise GovernanceViolation(
                f"loop detected: identical call to '{tool}' repeated {limit}x")
        self.recent_calls.append(fingerprint)

    def call(self, tool: str, **args):
        started = time.monotonic()
        try:
            self._check(tool, args)
        except GovernanceViolation as exc:
            self.status = "terminated"
            self._span(tool, args, started, "refused", str(exc))
            raise
        fn, side_effects = self.tools[tool]
        self.call_count += 1
        if self.dry_run and side_effects:
            self._span(tool, args, started, "simulated", None)
            return {"dry_run": True, "tool": tool}
        try:
            result = fn(**args)
        except Exception as exc:  # noqa: BLE001
            self._span(tool, args, started, "error", str(exc))
            raise
        if isinstance(result, dict):
            self.tokens_used += result.get("input_tokens", 0) + result.get("output_tokens", 0)
        self._span(tool, args, started, "ok", None)
        return result

    def _span(self, tool, args, started, outcome, detail):
        span = {
            "span": tool,
            "args": args,
            "ms": round((time.monotonic() - started) * 1000, 1),
            "outcome": outcome,
            "tokens_used_total": self.tokens_used,
            "call_n": self.call_count,
        }
        if detail:
            span["detail"] = detail
        self.spans.append(span)
        print(json.dumps(span), flush=True)

    def finish(self):
        if self.status == "running":
            self.status = "complete"
        return {
            "status": self.status,
            "tool_calls": self.call_count,
            "tokens": self.tokens_used,
            "seconds": round(time.monotonic() - self.started, 2),
            "dry_run": self.dry_run,
        }
```

The enrichment agent's capability manifest and budgets.

Create **`apps/agents/enrichment/manifest.json`**:

```json
{
  "agent": "enrichment",
  "description": "Classifies venues via the gateway and writes results, routing low-confidence output to human review.",
  "allowed_tools": ["lookup_venue", "classify", "write_classification", "queue_review"],
  "budgets": {
    "max_tokens_per_run": 20000,
    "max_wall_clock_seconds": 300,
    "max_tool_calls": 60
  },
  "loop_detection": {
    "identical_call_limit": 2
  },
  "confidence_threshold": 0.6
}
```

The enrichment agent: it looks up a venue, classifies it through the gateway, and either writes the result or sends a low-confidence result to a human review queue.

Create **`apps/agents/enrichment/agent.py`**:

```python
"""
The enrichment agent, running under the governance runtime.

Workflow per venue: look the venue up, classify it through the gateway,
then either write the classification (confidence above threshold) or
queue it for human review. Every step is a governed tool call.

    python agent.py --venue <id> [--dry-run]
    python agent.py --untagged [--dry-run] [--limit N]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import httpx
import redis as redis_lib

import sys as _sys; from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
from governance import GovernanceViolation, Governor

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8001")
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "dev-local-key")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
VENUES_FILE = os.getenv("VENUES_FILE", "/venues.json")

MANIFEST = json.load(open(Path(__file__).parent / "manifest.json"))
r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
_venues = {v["id"]: v for v in json.load(open(VENUES_FILE))}


def lookup_venue(venue_id: str) -> dict:
    v = _venues.get(venue_id)
    if not v:
        raise ValueError(f"unknown venue {venue_id}")
    return v


def classify(venue_id: str, description: str) -> dict:
    resp = httpx.post(
        f"{GATEWAY}/v1/classify",
        json={"venue_id": venue_id, "description": description},
        headers={"x-api-key": GATEWAY_KEY},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def write_classification(venue_id: str, vibes: list, confidence: float,
                         model: str, prompt_version: str) -> dict:
    r.hset("classifications", venue_id, json.dumps({
        "vibes": vibes, "confidence": confidence,
        "model": model, "prompt_version": prompt_version,
    }))
    return {"written": venue_id}


def queue_review(venue_id: str, vibes: list, confidence: float) -> dict:
    r.lpush("review:queue", json.dumps(
        {"venue_id": venue_id, "suggested": vibes, "confidence": confidence}))
    return {"queued": venue_id}


TOOLS = {
    "lookup_venue": (lookup_venue, False),
    "classify": (classify, False),          # spend, but no data mutation
    "write_classification": (write_classification, True),
    "queue_review": (queue_review, True),
}


def enrich(gov: Governor, venue_id: str):
    v = gov.call("lookup_venue", venue_id=venue_id)
    description = (f"{v['name']}. Type: {v.get('type_label') or 'unknown'}. "
                   f"Area: {v.get('area') or 'unknown'}. "
                   f"Price: {v.get('band_label') or 'unknown'}. "
                   f"Rating: {v.get('rating')} from {v.get('rating_count')} reviews.")
    c = gov.call("classify", venue_id=venue_id, description=description)
    if isinstance(c, dict) and c.get("dry_run"):
        return
    if c["confidence"] >= MANIFEST["confidence_threshold"]:
        gov.call("write_classification", venue_id=venue_id, vibes=c["vibes"],
                 confidence=c["confidence"], model=c["model"],
                 prompt_version=c["prompt_version"])
    else:
        gov.call("queue_review", venue_id=venue_id,
                 vibes=c["vibes"], confidence=c["confidence"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue")
    ap.add_argument("--untagged", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gov = Governor(MANIFEST, TOOLS, dry_run=args.dry_run)
    targets = ([args.venue] if args.venue else
               [v["id"] for v in _venues.values() if not v.get("tags")][:args.limit])
    try:
        for vid in targets:
            enrich(gov, vid)
    except GovernanceViolation as exc:
        print(json.dumps({"run": "terminated", "reason": str(exc)}), flush=True)
    print(json.dumps({"run_summary": gov.finish()}), flush=True)
    sys.exit(0 if gov.status == "complete" else 2)


if __name__ == "__main__":
    main()
```

A script that deliberately breaks the rules to prove each control refuses what it must.

Create **`apps/agents/enrichment/demo_violations.py`**:

```python
"""Prove the governance runtime refuses what it must refuse."""
import json

import sys as _sys; from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
from governance import GovernanceViolation, Governor

MANIFEST = json.load(open("manifest.json"))
noop = {t: (lambda **kw: {}, False) for t in MANIFEST["allowed_tools"]}
noop["delete_everything"] = (lambda **kw: {}, True)


def expect_violation(label, fn):
    try:
        fn()
        print(f"{label}: FAILED — call was allowed")
    except GovernanceViolation as exc:
        print(f"{label}: REFUSED — {exc}")


g1 = Governor(MANIFEST, noop)
expect_violation("undeclared tool", lambda: g1.call("delete_everything"))

tiny = json.loads(json.dumps(MANIFEST))
tiny["budgets"]["max_tool_calls"] = 2
g2 = Governor(tiny, noop)
g2.call("lookup_venue", venue_id="a")
g2.call("lookup_venue", venue_id="b")
expect_violation("tool-call budget", lambda: g2.call("lookup_venue", venue_id="c"))
print(json.dumps({"run_summary": g2.finish()}))

g3 = Governor(MANIFEST, noop)
g3.call("classify", venue_id="x", description="same")
g3.call("classify", venue_id="x", description="same")
expect_violation("loop detection", lambda: g3.call("classify", venue_id="x", description="same"))
```

The operations agent's manifest.

Create **`apps/agents/ops/manifest.json`**:

```json
{
  "agent": "ops",
  "description": "First-line incident triage: inspects the cluster read-only, retrieves runbooks, produces a diagnosis with evidence and opens a pull request. Never applies changes.",
  "allowed_tools": ["k8s_inspect", "runbook_lookup", "diagnose", "open_pr"],
  "budgets": {
    "max_tokens_per_run": 15000,
    "max_wall_clock_seconds": 240,
    "max_tool_calls": 25
  },
  "loop_detection": {
    "identical_call_limit": 2
  }
}
```

The operations agent: it inspects the cluster read-only, retrieves a runbook, asks the gateway for a diagnosis, and opens a pull request. It cannot change anything.

Create **`apps/agents/ops/agent.py`**:

```python
"""
The operations agent. Receives an alert, investigates the cluster with a
read-only service account, retrieves the matching runbook, asks the
gateway for a diagnosis grounded in the collected evidence, and opens a
pull request containing the diagnosis and proposed remediation. It never
applies a change directly.

    python agent.py --alert alert.json [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from governance import GovernanceViolation, Governor  # noqa: E402

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8001")
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "agent-local-key")
KUBECONFIG = os.getenv("OPS_KUBECONFIG", str(Path.home() / ".kube/ops-agent.yaml"))
REPO_ROOT = Path(__file__).resolve().parents[3]

MANIFEST = json.load(open(Path(__file__).parent / "manifest.json"))

ALLOWED_VERBS = {"get", "describe", "logs", "top"}


def k8s_inspect(verb: str, args: str, namespace: str) -> dict:
    """Read-only kubectl, doubly enforced: verb allowlist here, and the
    service account has no write verbs even if this check were bypassed."""
    if verb not in ALLOWED_VERBS:
        raise ValueError(f"verb '{verb}' is not read-only")
    cmd = ["kubectl", "--kubeconfig", KUBECONFIG, "-n", namespace, verb] + args.split()
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return {"stdout": out.stdout[-4000:], "stderr": out.stderr[-500:],
            "rc": out.returncode}


def runbook_lookup(alert_name: str) -> dict:
    path = REPO_ROOT / "runbooks" / f"{alert_name}.md"
    if path.exists():
        return {"found": True, "runbook": path.read_text()[:3000]}
    return {"found": False, "runbook": "no runbook for this alert"}


def diagnose(alert: dict, evidence: str, runbook: str) -> dict:
    prompt = f"""You are a first-line SRE triaging a Kubernetes alert. Using ONLY the evidence given, produce a diagnosis.

ALERT: {json.dumps(alert)}

EVIDENCE (kubectl output):
{evidence}

RUNBOOK:
{runbook}

Respond in markdown with exactly these sections:
## Symptom
## Root cause (cite specific evidence lines)
## Proposed remediation (the change a human should review and apply)
## Confidence (high/medium/low, one sentence why)"""
    req = urllib.request.Request(
        f"{GATEWAY}/v1/complete",
        data=json.dumps({"prompt": prompt, "purpose": "ops-triage",
                         "max_tokens": 1200}).encode(),
        headers={"x-api-key": GATEWAY_KEY, "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))


def open_pr(alert_name: str, diagnosis: str) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    branch = f"ops-agent/{alert_name.lower()}-{stamp}"
    rel = f"runbooks/diagnoses/{stamp}-{alert_name}.md"
    path = REPO_ROOT / rel
    path.parent.mkdir(exist_ok=True)
    path.write_text(diagnosis + "\n\n---\n*Opened autonomously by the ops agent. "
                    "A human must review and apply any remediation.*\n")
    run = lambda *c: subprocess.run(c, cwd=REPO_ROOT, capture_output=True,
                                    text=True, timeout=120)
    run("git", "checkout", "-b", branch)
    run("git", "add", rel)
    run("git", "commit", "-m", f"ops-agent: diagnosis for {alert_name}")
    run("git", "push", "-u", "origin", branch)
    pr = run("gh", "pr", "create", "--title",
             f"[ops-agent] {alert_name}: diagnosis and proposed remediation",
             "--body", diagnosis[:3000] + "\n\n---\n*Opened autonomously by the "
             "ops agent under its capability manifest. It has read-only cluster "
             "access and cannot apply this change.*")
    run("git", "checkout", "main")
    return {"branch": branch, "pr": pr.stdout.strip() or pr.stderr.strip()}


TOOLS = {
    "k8s_inspect": (k8s_inspect, False),
    "runbook_lookup": (runbook_lookup, False),
    "diagnose": (diagnose, False),
    "open_pr": (open_pr, True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    alert = json.load(open(args.alert))
    name = alert["labels"]["alertname"]
    ns = alert["labels"].get("namespace", "tamani-dev")

    gov = Governor(MANIFEST, TOOLS, dry_run=args.dry_run)
    try:
        pods = gov.call("k8s_inspect", verb="get", args="pods", namespace=ns)
        bad = [l.split()[0] for l in pods["stdout"].splitlines()[1:]
               if l and "Running" not in l and "Completed" not in l]
        evidence = ["$ kubectl get pods\n" + pods["stdout"]]
        for pod in bad[:3]:
            d = gov.call("k8s_inspect", verb="describe", args=f"pod {pod}", namespace=ns)
            evidence.append(f"$ kubectl describe pod {pod}\n" + d["stdout"][-2500:])
            lg = gov.call("k8s_inspect", verb="logs",
                          args=f"{pod} --tail=30 --all-containers", namespace=ns)
            evidence.append(f"$ kubectl logs {pod}\n" +
                            (lg["stdout"] or lg["stderr"])[-1500:])
        rb = gov.call("runbook_lookup", alert_name=name)
        diag = gov.call("diagnose", alert=alert, evidence="\n\n".join(evidence),
                        runbook=rb["runbook"] if isinstance(rb, dict) else "")
        if isinstance(diag, dict) and diag.get("dry_run"):
            print(json.dumps({"note": "dry run: diagnosis skipped"}))
        else:
            pr = gov.call("open_pr", alert_name=name, diagnosis=diag["text"])
            if not (isinstance(pr, dict) and pr.get("dry_run")):
                print(json.dumps({"pr": pr}))
    except GovernanceViolation as exc:
        print(json.dumps({"run": "terminated", "reason": str(exc)}))
    print(json.dumps({"run_summary": gov.finish()}))
    sys.exit(0 if gov.status == "complete" else 2)


if __name__ == "__main__":
    main()
```

The operations agent's read-only cluster identity, with no write permissions anywhere.

Create **`platform/k8s/tenancy/ops-agent.yaml`**:

```yaml
# The operations agent's identity: get, list, watch — and no write verb
# anywhere. Least privilege at the infrastructure boundary, not just the
# application one.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ops-agent
  namespace: tamani-dev
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ops-agent-readonly
rules:
  - apiGroups: [""]
    resources: [pods, pods/log, events, services, endpoints, configmaps]
    verbs: [get, list, watch]
  - apiGroups: [apps]
    resources: [deployments, replicasets, statefulsets]
    verbs: [get, list, watch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ops-agent
  namespace: tamani-dev
subjects:
  - { kind: ServiceAccount, name: ops-agent, namespace: tamani-dev }
roleRef:
  kind: ClusterRole
  name: ops-agent-readonly
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ops-agent
  namespace: tamani-prod
subjects:
  - { kind: ServiceAccount, name: ops-agent, namespace: tamani-dev }
roleRef:
  kind: ClusterRole
  name: ops-agent-readonly
  apiGroup: rbac.authorization.k8s.io
```

A runbook — a documented response procedure — that the operations agent retrieves during triage.

Create **`runbooks/KubePodNotReady.md`**:

```markdown
# KubePodNotReady

**Symptom:** a pod has been in a non-ready state (Pending, ImagePullBackOff,
CrashLoopBackOff, Error) for longer than the alert window.

**First three checks:**
1. `kubectl -n <ns> get pods` — which pod, which state, how many restarts.
2. `kubectl -n <ns> describe pod <pod>` — read Events at the bottom:
   image pull errors name the bad reference; scheduling failures name the
   unsatisfiable constraint; OOMKilled appears in last state.
3. `kubectl -n <ns> logs <pod> --previous` — the crash reason if the
   container starts and dies.

**Common causes:** a typo'd or unpushed image tag (ImagePullBackOff), a
failing readiness dependency, quota exhaustion (Pending with no node
assigned), a bad config or secret reference, OOMKilled from a limit set
too low.

**Escalation:** if the pod is managed by Argo CD, fix the manifest in Git
rather than editing live. Page a human if user-facing traffic is failing;
the ops agent must only propose changes by pull request.
```

**Check:** The gate blocks a regressing prompt; an undeclared tool, a budget breach and a loop are each refused; the operations agent opens a correct pull request without any ability to change the cluster.

---

# Phase 3 — Cloud infrastructure and GitOps

This phase moves the platform onto a real machine on the internet and makes it deploy itself from the repository. It requires an AWS account, a domain, and a provider key of your own.

## Cloud computing and AWS

Cloud computing means renting computers and services in a provider's data centre rather than owning hardware. Amazon Web Services (AWS) is the largest provider. This project rents a virtual machine, a fixed public address, a DNS service, storage for backups, and a store for secrets.

## Infrastructure as code

Infrastructure as code defines cloud resources in text files applied by a tool, rather than by clicking in a console. The definition lives in version control, can be reviewed, and can be rebuilt from scratch. Re-running the tool and seeing "no changes" proves the real infrastructure matches the definition, a state called no drift. This project uses OpenTofu, a free version of Terraform.

## DNS, TLS and certificates

DNS is the internet's directory, translating a name such as `platform.waypear.com` into a numeric address. TLS is the encryption behind the padlock in a browser, and a certificate proves a site is who it claims to be. Certificates are issued and renewed automatically by a certificate manager, at no cost, from Let's Encrypt.

## Continuous integration

Continuous integration is an automated pipeline that runs on every change: it tests the code, and on success builds and publishes the container images. Later phases add scanning, signing and an ingredient list to this pipeline.

## GitOps and image pinning

GitOps makes the repository the single source of truth for what should be running, with a program in the cluster continuously reconciling the live system to match it. Deployments become commits with a full history, and recovery is a matter of pointing the reconciler back at the repository. Production images are pinned by exact commit identifier, so what is running is precisely known. Argo CD is the reconciler used here.

## The infrastructure definitions

Declares that the AWS provider is used.

Create **`infra/terraform/providers.tf`**:

```hcl
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Local state until the S3 + DynamoDB backend is bootstrapped (Phase 0
  # completion step; requires the bucket to exist first).
}

provider "aws" {
  region = var.region
}
```

The inputs: the region, the domain, and your admin address and SSH key.

Create **`infra/terraform/variables.tf`**:

```hcl
variable "region" {
  type    = string
  default = "eu-west-2" # London, closest to Brighton traffic
}

variable "domain" {
  type    = string
  default = "waypear.com"
}

variable "instance_type" {
  type        = string
  default     = "t3.small"
  description = "2 GB RAM runs the core stack tightly; t3.medium (4 GB) is comfortable once observability and Argo CD land. Cost roughly doubles."
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed to reach ssh and the k8s api, e.g. your-ip/32"
}

variable "ssh_public_key" {
  type        = string
  description = "Public key for the admin keypair"
}
```

The resources: the virtual machine, its fixed address, the DNS zone and records, and the backup storage.

Create **`infra/terraform/main.tf`**:

```hcl
# Tamani platform node: a single EC2 instance running k3s, fronted by an
# Elastic IP, with DNS under platform.waypear.com. Applied only after cost
# is confirmed. State starts local; the S3 backend is bootstrapped later.

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_security_group" "node" {
  name        = "tamani-node"
  description = "k3s single node: ssh, http, https, k8s api"

  dynamic "ingress" {
    for_each = { ssh = 22, http = 80, https = 443, k8s_api = 6443 }
    content {
      description = ingress.key
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ingress.key == "ssh" || ingress.key == "k8s_api" ? [var.admin_cidr] : ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_key_pair" "admin" {
  key_name   = "tamani-admin"
  public_key = var.ssh_public_key
}

resource "aws_instance" "node" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.admin.key_name
  vpc_security_group_ids = [aws_security_group.node.id]
  user_data              = file("${path.module}/user_data.sh")

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  tags = { Name = "tamani-platform-node" }
}

resource "aws_eip" "node" {
  instance = aws_instance.node.id
}

resource "aws_route53_zone" "waypear" {
  name = var.domain
}

resource "aws_route53_record" "platform" {
  zone_id = aws_route53_zone.waypear.zone_id
  name    = "platform.${var.domain}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.node.public_ip]
}

resource "aws_route53_record" "wildcard" {
  zone_id = aws_route53_zone.waypear.zone_id
  name    = "*.platform.${var.domain}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.node.public_ip]
}

resource "aws_s3_bucket" "backups" {
  bucket_prefix = "tamani-backups-"
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    filter {}
    expiration { days = 30 }
  }
}
```

The values printed after applying, including the four nameservers to set at your registrar.

Create **`infra/terraform/outputs.tf`**:

```hcl
output "node_ip" {
  value = aws_eip.node.public_ip
}

output "platform_fqdn" {
  value = aws_route53_record.platform.fqdn
}

output "nameservers" {
  description = "Set these at the waypear.com registrar to delegate DNS to Route53"
  value       = aws_route53_zone.waypear.name_servers
}

output "backup_bucket" {
  value = aws_s3_bucket.backups.bucket
}
```

The script the machine runs on first boot to install the lightweight Kubernetes (k3s) with a certificate valid for remote access.

Create **`infra/terraform/user_data.sh`**:

```bash
#!/usr/bin/env bash
# Bootstraps k3s on first boot. Traefik disabled: ingress-nginx is the
# planned edge per the project plan. The public IP is fetched from IMDS
# so the API server cert is valid for remote kubectl from day one.
set -euo pipefail
# Swap before anything else: a 2 GiB node without swap thrashes to
# lockup under deploy surge (see postmortem 2026-07-23).
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
mkdir -p /etc/rancher/k3s
cat > /etc/rancher/k3s/config.yaml <<EOF
tls-san:
  - ${PUBLIC_IP}
  - platform.waypear.com
EOF
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
```


```bash
cd infra/terraform && tofu init && tofu plan -out=tfplan
tofu apply tfplan
# set the four output nameservers at your domain registrar
tofu plan   # expect: No changes
```

## The GitOps definitions

The single application applied by hand; it defines all the others, so the whole platform bootstraps from one file.

Create **`platform/argocd/root.yaml`**:

```yaml
# App-of-apps: this single Application makes Argo CD manage everything
# under platform/argocd/apps, which in turn defines the whole platform.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/argocd/apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Tells Argo CD to keep the namespaces, quotas and roles in sync automatically.

Create **`platform/argocd/apps/tenancy.yaml`**:

```yaml
# Sync wave -1: namespaces, quotas and rbac reconcile before anything
# that depends on them.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: tenancy
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/tenancy
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

The production workloads, which require a deliberate manual sync to change.

Create **`platform/argocd/apps/workloads-prod.yaml`**:

```yaml
# Production workloads: NO automated sync. Promotion is a deliberate
# act — a human syncs after reviewing what would change.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: workloads-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: tamani-prod
  syncPolicy:
    syncOptions:
      - PruneLast=true
```

The ingress controller that receives outside traffic.

Create **`platform/argocd/apps/ingress-nginx.yaml`**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ingress-nginx
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://kubernetes.github.io/ingress-nginx
    chart: ingress-nginx
    targetRevision: 4.11.3
    helm:
      valuesObject:
        controller:
          resources:
            requests: { cpu: 50m, memory: 90Mi }
  destination:
    server: https://kubernetes.default.svc
    namespace: ingress-nginx
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

The certificate manager that issues TLS certificates.

Create **`platform/argocd/apps/cert-manager.yaml`**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cert-manager
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://charts.jetstack.io
    chart: cert-manager
    targetRevision: v1.16.2
    helm:
      valuesObject:
        crds:
          enabled: true
        resources:
          requests: { cpu: 25m, memory: 64Mi }
        webhook:
          resources:
            requests: { cpu: 25m, memory: 32Mi }
        cainjector:
          resources:
            requests: { cpu: 25m, memory: 64Mi }
  destination:
    server: https://kubernetes.default.svc
    namespace: cert-manager
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Create **`platform/argocd/apps/edge.yaml`**:

```yaml
# Wave 1: issuer and ingress apply only after ingress-nginx and
# cert-manager (wave 0) are healthy.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: edge
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/edge
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    retry:
      limit: 5
      backoff:
        duration: 30s
        factor: 2
```

Configures automatic certificates from Let's Encrypt.

Create **`platform/k8s/edge/cluster-issuer.yaml`**:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: maicymaritim@gmail.com
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

Routes the domain to the API and requests a certificate for it.

Create **`platform/k8s/edge/api-ingress.yaml`**:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tamani-api
  namespace: tamani-prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt
    nginx.ingress.kubernetes.io/limit-rps: "20"
spec:
  ingressClassName: nginx
  tls:
    - hosts: [platform.waypear.com]
      secretName: platform-waypear-tls
  rules:
    - host: platform.waypear.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: tamani-api
                port:
                  number: 80
```

Opens exactly the paths the edge needs through the default-deny policy.

Create **`platform/k8s/edge/netpol-edge.yaml`**:

```yaml
# The prod namespace default-denies ingress; these open exactly what the
# edge needs: nginx -> api, and nginx -> ACME http01 solver pods.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-nginx-to-api
  namespace: tamani-prod
spec:
  podSelector:
    matchLabels: { app: tamani-api }
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 8000
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-acme-solver
  namespace: tamani-prod
spec:
  podSelector:
    matchLabels:
      acme.cert-manager.io/http01-solver: "true"
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 8089
```

The pipeline: test, then build, push, scan, generate an ingredient list, and sign the images (scanning and signing are explained in Phase 8).

Create **`.github/workflows/ci.yml`**:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

env:
  REGISTRY: ghcr.io
  OWNER: maicymxtim

jobs:
  secrets-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: api unit tests
        run: |
          pip install -q -r apps/api/requirements.txt pytest httpx
          python -m pytest apps/api/tests -q

  build:
    needs: test
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write   # cosign keyless signing
    strategy:
      matrix:
        app: [api, gateway, worker]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        id: build
        with:
          context: apps/${{ matrix.app }}
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.OWNER }}/tamani-${{ matrix.app }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.OWNER }}/tamani-${{ matrix.app }}:main
          cache-from: type=gha
          cache-to: type=gha,mode=max

      # Fail the build on fixable critical vulnerabilities. Exceptions go
      # in .trivyignore with an expiry comment — explicit and time-limited.
      - name: trivy vulnerability scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.OWNER }}/tamani-${{ matrix.app }}:${{ github.sha }}
          severity: CRITICAL
          ignore-unfixed: true
          exit-code: "1"
          trivyignores: .trivyignore

      - name: sbom
        uses: anchore/sbom-action@v0.17.8
        with:
          image: ${{ env.REGISTRY }}/${{ env.OWNER }}/tamani-${{ matrix.app }}:${{ github.sha }}
          artifact-name: sbom-tamani-${{ matrix.app }}.spdx.json

      - name: cosign sign (keyless)
        uses: sigstore/cosign-installer@v3.7.0
      - run: cosign sign --yes ${{ env.REGISTRY }}/${{ env.OWNER }}/tamani-${{ matrix.app }}@${{ steps.build.outputs.digest }}
```

**Check:** `tofu plan` reports no changes; Argo CD shows the applications synced and healthy; the domain serves over HTTPS.

---

# Phase 7 — Observability and service level objectives

This phase adds the ability to see the system's health and to define what healthy means.

## Observability

Observability is the ability to understand a system's internal state from its outputs. Three kinds of signal support it: metrics (numbers over time, such as requests per second), logs (records of events) and traces (the path of one request across services).

## Service level objectives and error budgets

A service level indicator is a measured ratio of good events to valid events. A service level objective is a target for it, such as 99.5% of requests succeeding over a month. The error budget is the small amount of failure the objective allows. The burn rate is how fast that budget is being spent; alerting on burn rate — a fast burn paging immediately, a slow burn raising a ticket — removes most alert noise.

## The monitoring definitions

Installs Prometheus, Grafana and the alerting components, sized for a small node.

Create **`platform/argocd/apps/monitoring.yaml`**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: monitoring
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: 65.5.1
    helm:
      valuesObject:
        # Trimmed for a single 4 GB node: short retention, tight limits.
        prometheus:
          prometheusSpec:
            retention: 24h
            resources:
              requests: { cpu: 100m, memory: 400Mi }
              limits: { memory: 700Mi }
            serviceMonitorSelectorNilUsesHelmValues: false
            ruleSelectorNilUsesHelmValues: false
        alertmanager:
          alertmanagerSpec:
            resources:
              requests: { cpu: 10m, memory: 32Mi }
              limits: { memory: 64Mi }
        grafana:
          adminPassword: tamani-grafana
          resources:
            requests: { cpu: 50m, memory: 96Mi }
            limits: { memory: 192Mi }
          sidecar:
            dashboards: { enabled: true, searchNamespace: ALL }
          additionalDataSources:
            - name: Loki
              type: loki
              uid: loki
              url: http://loki.monitoring:3100
        kube-state-metrics:
          resources:
            requests: { cpu: 10m, memory: 32Mi }
            limits: { memory: 96Mi }
        nodeExporter: { enabled: true }
        # One-node cluster: no HA components needed.
        defaultRules:
          rules:
            alertmanager: false
            etcd: false
            kubeProxy: false
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true, ServerSideApply=true]
```

Installs Loki, which stores logs for searching.

Create **`platform/argocd/apps/loki.yaml`**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: loki
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://grafana.github.io/helm-charts
    chart: loki-stack
    targetRevision: 2.10.2
    helm:
      valuesObject:
        loki:
          isDefault: false
          resources:
            requests: { cpu: 50m, memory: 128Mi }
            limits: { memory: 256Mi }
          config:
            table_manager:
              retention_deletes_enabled: true
              retention_period: 72h
        promtail:
          resources:
            requests: { cpu: 20m, memory: 48Mi }
            limits: { memory: 96Mi }
        grafana: { enabled: false }
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true]
```

Create **`platform/argocd/apps/slo.yaml`**:

```yaml
# Wave 1: needs the ServiceMonitor/PrometheusRule CRDs from monitoring.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: slo
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/slo
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    retry:
      limit: 5
      backoff: { duration: 30s, factor: 2 }
```

Tells Prometheus to collect metrics from the API and gateway.

Create **`platform/k8s/slo/servicemonitors.yaml`**:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: tamani-api
  namespace: tamani-prod
spec:
  selector:
    matchLabels: { app: tamani-api }
  endpoints:
    - targetPort: 8000
      path: /metrics
      interval: 30s
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: tamani-gateway
  namespace: tamani-prod
spec:
  selector:
    matchLabels: { app: tamani-gateway }
  endpoints:
    - targetPort: 8001
      path: /metrics
      interval: 30s
```

Allows the monitoring namespace through the default-deny policy so it can collect metrics.

Create **`platform/k8s/slo/netpol-monitoring.yaml`**:

```yaml
# Prometheus lives in the monitoring namespace; the prod default-deny
# would silently break scraping. Open exactly the metrics ports.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-prometheus-scrape
  namespace: tamani-prod
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
      ports:
        - port: 8000
        - port: 8001
```

Defines the objectives and the burn-rate alerts.

Create **`platform/k8s/slo/slo-rules.yaml`**:

```yaml
# The service level objectives, as code.
#
#   Availability: 99.5% of API requests succeed, over 30 days.
#   Latency:      95% of API requests complete under 400 ms.
#
# Alerting is multi-window multi-burn-rate: a fast burn (would spend 2%+
# of the monthly error budget in an hour) pages immediately; a slow burn
# (10% over three days) raises a ticket. This removes most alert noise:
# a blip trips neither, a real fire trips the fast pair.
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: tamani-slo
  namespace: tamani-prod
spec:
  groups:
    - name: tamani.slo.recording
      interval: 30s
      rules:
        - record: tamani:api_error_ratio:rate5m
          expr: |
            (sum(rate(http_requests_total{namespace="tamani-prod", status=~"5.."}[5m])) or vector(0))
            / clamp_min(sum(rate(http_requests_total{namespace="tamani-prod"}[5m])), 1e-9)
        - record: tamani:api_error_ratio:rate1h
          expr: |
            (sum(rate(http_requests_total{namespace="tamani-prod", status=~"5.."}[1h])) or vector(0))
            / clamp_min(sum(rate(http_requests_total{namespace="tamani-prod"}[1h])), 1e-9)
        - record: tamani:api_error_ratio:rate6h
          expr: |
            (sum(rate(http_requests_total{namespace="tamani-prod", status=~"5.."}[6h])) or vector(0))
            / clamp_min(sum(rate(http_requests_total{namespace="tamani-prod"}[6h])), 1e-9)
        - record: tamani:api_p95_seconds:rate10m
          expr: |
            histogram_quantile(0.95, sum by (le)
              (rate(http_request_duration_seconds_bucket{namespace="tamani-prod", handler!="/metrics"}[10m])))

    - name: tamani.slo.alerts
      rules:
        - alert: TamaniErrorBudgetFastBurn
          expr: |
            tamani:api_error_ratio:rate5m > (14.4 * 0.005)
            and tamani:api_error_ratio:rate1h > (14.4 * 0.005)
          for: 2m
          labels: { severity: critical, namespace: tamani-prod }
          annotations:
            summary: "API burning >2% of monthly error budget per hour"
            runbook: runbooks/TamaniErrorBudgetFastBurn.md
        - alert: TamaniErrorBudgetSlowBurn
          expr: |
            tamani:api_error_ratio:rate6h > (1.0 * 0.005)
          for: 30m
          labels: { severity: warning, namespace: tamani-prod }
          annotations:
            summary: "API error rate would exhaust monthly budget"
            runbook: runbooks/TamaniErrorBudgetFastBurn.md
        - alert: TamaniLatencySLOBreach
          expr: tamani:api_p95_seconds:rate10m > 0.4
          for: 15m
          labels: { severity: warning, namespace: tamani-prod }
          annotations:
            summary: "API p95 latency above the 400ms objective"
            runbook: runbooks/TamaniLatencySLOBreach.md
```

The service-health and spend dashboards.

Create **`platform/k8s/slo/dashboards.yaml`**:

```yaml
# Two dashboards, loaded by Grafana's sidecar. Generated JSON —
# regenerate via the script in git history if editing.
apiVersion: v1
kind: ConfigMap
metadata:
  name: dashboard-tamani-service
  namespace: tamani-prod
  labels: { grafana_dashboard: "1" }
data:
  tamani-service.json: |
    {
     "title": "Tamani \u2014 Service Health",
     "uid": "tamani-svc",
     "timezone": "browser",
     "editable": true,
     "time": {
      "from": "now-6h",
      "to": "now"
     },
     "refresh": "30s",
     "schemaVersion": 39,
     "version": 1,
     "panels": [
      {
       "id": 1,
       "type": "stat",
       "title": "Availability (5m)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "1 - tamani:api_error_ratio:rate5m"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "percentunit",
         "decimals": 3,
         "thresholds": {
          "mode": "absolute",
          "steps": [
           {
            "color": "red",
            "value": null
           },
           {
            "color": "yellow",
            "value": 0.99
           },
           {
            "color": "green",
            "value": 0.995
           }
          ]
         }
        },
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 2,
       "type": "stat",
       "title": "p95 latency",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 6,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "tamani:api_p95_seconds:rate10m"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "s",
         "decimals": 3,
         "thresholds": {
          "mode": "absolute",
          "steps": [
           {
            "color": "green",
            "value": null
           },
           {
            "color": "red",
            "value": 0.4
           }
          ]
         }
        },
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 3,
       "type": "stat",
       "title": "Error budget left (30d)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 12,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "clamp_min(1 - ((sum(increase(http_requests_total{namespace=\"tamani-prod\", status=~\"5..\"}[30d])) or vector(0)) / clamp_min(sum(increase(http_requests_total{namespace=\"tamani-prod\"}[30d])) * 0.005, 1e-9)), 0)"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "percentunit",
         "decimals": 1,
         "thresholds": {
          "mode": "absolute",
          "steps": [
           {
            "color": "red",
            "value": null
           },
           {
            "color": "yellow",
            "value": 0.2
           },
           {
            "color": "green",
            "value": 0.5
           }
          ]
         }
        },
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 4,
       "type": "stat",
       "title": "Pod restarts (24h)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 18,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum(increase(kube_pod_container_status_restarts_total{namespace=~\"tamani-.*\"}[24h]))"
        }
       ],
       "fieldConfig": {
        "defaults": {},
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 5,
       "type": "timeseries",
       "title": "Request rate by status",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 0,
        "y": 5,
        "w": 12,
        "h": 8
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum by (status) (rate(http_requests_total{namespace=\"tamani-prod\"}[5m]))",
         "legendFormat": "{{status}}"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "reqps"
        },
        "overrides": []
       }
      },
      {
       "id": 6,
       "type": "timeseries",
       "title": "Node memory working set",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 12,
        "y": 5,
        "w": 12,
        "h": 8
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
         "legendFormat": "used"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "bytes"
        },
        "overrides": []
       }
      }
     ]
    }
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: dashboard-tamani-spend
  namespace: tamani-prod
  labels: { grafana_dashboard: "1" }
data:
  tamani-spend.json: |
    {
     "title": "Tamani \u2014 AI Spend",
     "uid": "tamani-spend",
     "timezone": "browser",
     "editable": true,
     "time": {
      "from": "now-24h",
      "to": "now"
     },
     "refresh": "1m",
     "schemaVersion": 39,
     "version": 1,
     "panels": [
      {
       "id": 1,
       "type": "stat",
       "title": "Spend (24h)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum(increase(gateway_spend_usd_total[24h]))"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "currencyUSD",
         "decimals": 4
        },
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 2,
       "type": "stat",
       "title": "Saved by cache (24h)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 6,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum(increase(gateway_saved_usd_total[24h]))"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "currencyUSD",
         "decimals": 4
        },
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 3,
       "type": "stat",
       "title": "Cache hit rate (24h)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 12,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum(increase(gateway_cache_hits_total[24h])) / clamp_min(sum(increase(gateway_cache_hits_total[24h])) + sum(increase(gateway_cache_misses_total[24h])), 1)"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "percentunit",
         "decimals": 1
        },
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 4,
       "type": "stat",
       "title": "Tokens (24h)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 18,
        "y": 0,
        "w": 6,
        "h": 5
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum(increase(gateway_tokens_total[24h]))"
        }
       ],
       "fieldConfig": {
        "defaults": {},
        "overrides": []
       },
       "options": {
        "reduceOptions": {
         "calcs": [
          "lastNotNull"
         ]
        }
       }
      },
      {
       "id": 5,
       "type": "timeseries",
       "title": "Spend by purpose ($/h)",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 0,
        "y": 5,
        "w": 12,
        "h": 8
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum by (purpose) (increase(gateway_spend_usd_total[1h]))",
         "legendFormat": "{{purpose}}"
        }
       ],
       "fieldConfig": {
        "defaults": {
         "unit": "currencyUSD"
        },
        "overrides": []
       }
      },
      {
       "id": 6,
       "type": "timeseries",
       "title": "Tokens by purpose",
       "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
       },
       "gridPos": {
        "x": 12,
        "y": 5,
        "w": 12,
        "h": 8
       },
       "targets": [
        {
         "refId": "A",
         "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
         },
         "expr": "sum by (purpose, direction) (increase(gateway_tokens_total[1h]))",
         "legendFormat": "{{purpose}} {{direction}}"
        }
       ],
       "fieldConfig": {
        "defaults": {},
        "overrides": []
       }
      }
     ]
    }
```

Create **`runbooks/TamaniErrorBudgetFastBurn.md`**:

```markdown
# TamaniErrorBudgetFastBurn

**Symptom:** the API is failing enough requests to spend over 2% of the
monthly error budget per hour. Users are seeing errors right now.

**First three checks:**
1. Grafana "Tamani — Service Health": which status codes are rising?
2. `kubectl -n tamani-prod get pods` — restarts or not-ready pods?
3. Loki: filter `{namespace="tamani-prod"}` for level=ERROR around onset.

**Common causes:** a bad deploy (check Argo CD history, roll back by
reverting the Git pin), a dependency outage (Redis, provider), node
memory pressure (check the memory panel).

**Escalation:** revert the last promotion commit first, ask questions
after. The ops agent may already have opened a PR with a diagnosis.
```

Create **`runbooks/TamaniLatencySLOBreach.md`**:

```markdown
# TamaniLatencySLOBreach

**Symptom:** p95 latency above 400ms for 15 minutes.

**First three checks:**
1. Grafana: is request rate up (load) or flat (regression)?
2. `kubectl -n tamani-prod top pods` — CPU throttling near limits?
3. Loki: slow-request logs; check correlation ids of slow paths.

**Common causes:** CPU limits too low after a traffic rise, a slow
dependency call on the hot path, node swap pressure.

**Escalation:** raise replica count or CPU limits via Git if load-driven;
otherwise treat as a regression and bisect recent promotions.
```

**Check:** Prometheus lists the services as reachable; the objective rules return values; the dashboards show availability, latency and spend.

---

# Phase 8 — Security and supply chain

This phase ensures only trusted, scanned, signed software runs, and that secrets never sit in the repository or in a human's command history.

## Supply chain security

The software supply chain is everything that goes into a running image. Securing it means proving where each image came from and what it contains, and refusing anything untrusted.

## Image signing

Image signing attaches a verifiable signature to an image, proving its origin. Keyless signing ties the signature to the identity of the pipeline that built it, rather than to a stored key that could leak. The cluster verifies the signature before allowing an image to run and refuses unsigned ones.

## Vulnerability scanning and SBOMs

A vulnerability scan checks an image against a database of known security flaws, and the pipeline fails on serious fixable ones. A software bill of materials (SBOM) is a list of everything inside an image, produced for every build, so its contents can be audited.

## Secret management

A secret is a sensitive value such as an API key. Secrets must not live in the repository. Instead they live in a managed store, and an operator syncs them into the cluster using an identity that can only read them. Rotation becomes updating the store; the change propagates on its own.

## The security definitions

Installs the admission controller on the cloud cluster and applies the policies.

Create **`platform/argocd/apps/kyverno.yaml`**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kyverno
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://kyverno.github.io/kyverno/
    chart: kyverno
    targetRevision: 3.3.4
    helm:
      valuesObject:
        # Admission control only on the small node — no background scans,
        # no policy reports, single replica.
        admissionController:
          replicas: 1
          container:
            resources:
              requests: { cpu: 50m, memory: 128Mi }
              limits: { memory: 384Mi }
        backgroundController: { enabled: false }
        reportsController: { enabled: false }
        cleanupController: { enabled: false }
  destination:
    server: https://kubernetes.default.svc
    namespace: kyverno
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true, ServerSideApply=true]
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: policies
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/policies
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    retry:
      limit: 5
      backoff: { duration: 30s, factor: 2 }
```

Requires a valid signature from this project's pipeline for images from its registry; unsigned images are refused.

Create **`platform/policies/verify-images.yaml`**:

```yaml
# Supply chain enforcement: any image from our registry entering a
# tamani namespace must carry a valid keyless signature produced by this
# repository's CI on main. An unsigned or tampered image is refused at
# admission. Third-party images (redis, nats) are out of scope here —
# they are pinned by tag and vetted by Renovate instead.
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signatures
spec:
  validationFailureAction: Enforce
  webhookTimeoutSeconds: 30
  failurePolicy: Fail
  rules:
    - name: require-cosign-signature
      match:
        any:
          - resources:
              kinds: [Pod]
              namespaceSelector:
                matchExpressions:
                  - { key: env, operator: In, values: [dev, staging, prod] }
      verifyImages:
        - imageReferences: ["ghcr.io/maicymxtim/*"]
          failureAction: Enforce
          attestors:
            - entries:
                - keyless:
                    subject: "https://github.com/MaicyMxtim/tamani-platform/.github/workflows/*@refs/heads/main"
                    issuer: "https://token.actions.githubusercontent.com"
                    rekor:
                      url: https://rekor.sigstore.dev
```

A cloud identity for the secrets operator, able only to read the project's secret path.

Create **`infra/terraform/eso.tf`**:

```hcl
# Identity for External Secrets Operator: read-only access to the
# /tamani/* path in SSM Parameter Store, nothing else. The secret VALUES
# are put into SSM out-of-band (never through Terraform state).

resource "aws_iam_user" "eso" {
  name = "tamani-eso-reader"
}

resource "aws_iam_user_policy" "eso_ssm_read" {
  name = "ssm-read-tamani"
  user = aws_iam_user.eso.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
      Resource = "arn:aws:ssm:${var.region}:*:parameter/tamani/*"
    }]
  })
}

resource "aws_iam_access_key" "eso" {
  user = aws_iam_user.eso.name
}

output "eso_access_key_id" {
  value     = aws_iam_access_key.eso.id
  sensitive = true
}

output "eso_secret_access_key" {
  value     = aws_iam_access_key.eso.secret
  sensitive = true
}
```

Installs the operator that syncs secrets into the cluster.

Create **`platform/argocd/apps/external-secrets.yaml`**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: external-secrets
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://charts.external-secrets.io
    chart: external-secrets
    targetRevision: 0.10.5
    helm:
      valuesObject:
        resources:
          requests: { cpu: 20m, memory: 48Mi }
          limits: { memory: 128Mi }
        webhook:
          resources: { requests: { cpu: 10m, memory: 24Mi }, limits: { memory: 64Mi } }
        certController:
          resources: { requests: { cpu: 10m, memory: 24Mi }, limits: { memory: 64Mi } }
  destination:
    server: https://kubernetes.default.svc
    namespace: external-secrets
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true]
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: secrets
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/secrets
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    retry:
      limit: 5
      backoff: { duration: 30s, factor: 2 }
```

Defines where the provider key lives in the cloud secret store and how it is synced into the cluster hourly.

Create **`platform/k8s/secrets/anthropic.yaml`**:

```yaml
# The provider key never exists in Git or in a human's kubectl history:
# it lives in AWS SSM Parameter Store and ESO materialises it in-cluster,
# refreshing hourly so rotation in SSM propagates on its own.
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-ssm
spec:
  provider:
    aws:
      service: ParameterStore
      region: eu-west-2
      auth:
        secretRef:
          accessKeyIDSecretRef:
            name: eso-aws-creds
            namespace: external-secrets
            key: access-key-id
          secretAccessKeySecretRef:
            name: eso-aws-creds
            namespace: external-secrets
            key: secret-access-key
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: anthropic
  namespace: tamani-prod
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-ssm
    kind: ClusterSecretStore
  target:
    name: anthropic
    creationPolicy: Owner
  data:
    - secretKey: api-key
      remoteRef:
        key: /tamani/anthropic-api-key
```

Place the key in the cloud secret store, out of band, never in the repository.


```bash
aws ssm put-parameter --name /tamani/anthropic-api-key \
  --type SecureString --value "$YOUR_KEY" --overwrite
```

**Check:** An unsigned image is refused at admission; a signed image is admitted; the cluster secret matches the value in the store.

---

# Phase 9 — Reliability proof

This phase measures the platform's limits and confirms its failure behaviour, recording the evidence.

## Load testing, saturation and limiting resources

A load test drives controlled traffic to measure capacity and response time. The saturation point is the load at which a resource is exhausted; the limiting resource is the one that runs out first. Knowing both replaces guessing at capacity.

## Chaos engineering

Chaos engineering deliberately injects a fault — killing a pod, adding delay — with a written prediction of the outcome, then records the result against the prediction. It reveals whether the system's safety mechanisms actually work.

## Postmortems, runbooks and disruption budgets

A postmortem is a blameless write-up of an incident focused on why the system permitted the failure, not who caused it. A runbook is a documented response for an alert. A pod disruption budget guarantees a minimum number of copies survive a voluntary disruption, so planned events do not cause an outage.

## The load profile

The load-test script, mixing searches and feed reads and raising the number of simulated users in stages.

Create **`tools/load/api-load.js`**:

```javascript
// k6 load profile for the venue API: a realistic mix of searches and
// feed reads. BASE_URL decides whether this tests the public edge
// (rate-limited) or the in-cluster service (raw capacity).
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://tamani-api";

export const options = {
  stages: [
    { duration: "30s", target: Number(__ENV.VUS_LOW || 10) },
    { duration: "90s", target: Number(__ENV.VUS_HIGH || 60) },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<400"],
  },
};

const paths = [
  "/venues?vibe=drinks&limit=10",
  "/venues?vibe=coffee&limit=10",
  "/venues?area=lanes&limit=10",
  "/venues?band=under_5&limit=10",
  "/feed?limit=20",
  "/health/live",
];

export default function () {
  const res = http.get(`${BASE}${paths[Math.floor(Math.random() * paths.length)]}`);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(Math.random() * 0.5);
}
```

Run the load test, raising it until a resource saturates, and record the saturation point and limiting resource. (`k6` is the load-testing tool.)


```bash
BASE_URL=https://<your-domain> VUS_LOW=5 VUS_HIGH=30 k6 run tools/load/api-load.js
```

Then, under light load, kill an API pod (expecting no user-visible errors) and the single gateway (timing the outage and automatic recovery), recording each experiment's prediction and result in `runbooks/chaos/`, and any incident in `runbooks/postmortems/`.

**Check:** The load test names the saturation point and limiting resource; the API pod kill causes no errors; the gateway kill recovers on its own; the results are written up.

---

# Phase 10 — Developer self-service

This phase provides a single command that creates a complete, operable service, which is what makes the whole system an internal developer platform.

## Internal developer platforms and golden paths

An internal developer platform lets developers create and run services without needing to understand the cluster's internals. A golden path is the supported, standard way to build a service. Because the standard way supplies operability by default, a service built on it cannot ship without health checks, monitoring, security and a runbook.

## Scaffolding and templates

Scaffolding generates a complete service from a template — a parameterised set of source files. The generated output includes the hardened container, probes, metrics, network policy, monitoring, a signed pipeline, a deployment definition and a runbook, so correctness is the default rather than extra work.

## The CLI and templates

The platform command-line tool. `tamani new <name>` scaffolds a service; other commands list and remove services.

Create **`cli/tamani`**:

```text
#!/usr/bin/env python3
"""tamani — the platform CLI.

    tamani new <name> [--port 8000] [--owner you]   scaffold a service
    tamani catalogue                                 list every service
    tamani status <name>                             pods + argo state
    tamani destroy <name>                            remove a service

`new` writes every file a service needs to be operable on day one:
hardened Dockerfile, split probes, JSON logs, metrics, NetworkPolicy,
ServiceMonitor, an error-rate alert, signed CI, an Argo CD application
and a runbook stub. Commit and push; Argo does the rest. A developer on
the golden path cannot ship a service without operability, because the
template supplies it.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "templates"
GOLDEN_VERSION = "gp-1.0.0"


def render(tpl: str, ctx: dict) -> str:
    out = (TEMPLATES / tpl).read_text()
    for k, v in ctx.items():
        out = out.replace(f"__{k}__", str(v))
    return out


def new(args):
    name = args.name
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,30}", name):
        sys.exit("name must be lowercase-kebab, 3-31 chars")
    if (ROOT / "apps" / name).exists():
        sys.exit(f"apps/{name} already exists")
    ctx = {
        "NAME": name,
        "PORT": args.port,
        "OWNER": args.owner,
        "DATE": time.strftime("%Y-%m-%d"),
        "GOLDEN_VERSION": GOLDEN_VERSION,
        "ALERTNAME": "".join(p.capitalize() for p in name.split("-")),
    }
    files = {
        f"apps/{name}/main.py": "main.py.tpl",
        f"apps/{name}/Dockerfile": "Dockerfile.tpl",
        f"apps/{name}/requirements.txt": "requirements.txt.tpl",
        f"platform/k8s/services/{name}/{name}.yaml": "k8s.yaml.tpl",
        f"platform/k8s/services/{name}/catalogue.yaml": "catalogue.yaml.tpl",
        f"platform/argocd/apps/svc-{name}.yaml": "argo-app.yaml.tpl",
        f".github/workflows/svc-{name}.yml": "ci.yml.tpl",
        f"runbooks/{name}.md": "runbook.md.tpl",
    }
    for dest, tpl in files.items():
        path = ROOT / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(tpl, ctx))
        print(f"  wrote {dest}")
    print(f"\n{name} scaffolded on golden path {GOLDEN_VERSION}.")
    print("next: git add -A && git commit && git push — Argo deploys it to dev.")


def catalogue(_args):
    import json
    rows = []
    for f in sorted(ROOT.glob("platform/k8s/services/*/catalogue.yaml")):
        entry = {}
        for line in f.read_text().splitlines():
            if ":" in line and not line.startswith(" "):
                k, _, v = line.partition(":")
                entry[k.strip()] = v.strip().strip('"')
        rows.append(entry)
    if not rows:
        print("no services on the golden path yet")
        return
    print(f"{'service':<18} {'owner':<16} {'golden path':<12} {'runbook'}")
    for r in rows:
        print(f"{r.get('name',''):<18} {r.get('owner',''):<16} "
              f"{r.get('golden_path',''):<12} {r.get('runbook','')}")


def status(args):
    subprocess.run(["kubectl", "-n", "tamani-dev", "get", "pods,svc",
                    "-l", f"app={args.name}"])


def destroy(args):
    name = args.name
    removed = []
    for p in [f"apps/{name}", f"platform/k8s/services/{name}",
              f"platform/argocd/apps/svc-{name}.yaml",
              f".github/workflows/svc-{name}.yml", f"runbooks/{name}.md"]:
        full = ROOT / p
        if full.exists():
            subprocess.run(["git", "-C", str(ROOT), "rm", "-rq", p])
            removed.append(p)
    print("removed: " + ", ".join(removed))
    print("commit and push; Argo prunes the live resources.")


def main():
    ap = argparse.ArgumentParser(prog="tamani")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("name")
    p_new.add_argument("--port", type=int, default=8000)
    p_new.add_argument("--owner", default="maicy")
    p_new.set_defaults(fn=new)
    sub.add_parser("catalogue").set_defaults(fn=catalogue)
    p_st = sub.add_parser("status")
    p_st.add_argument("name")
    p_st.set_defaults(fn=status)
    p_de = sub.add_parser("destroy")
    p_de.add_argument("name")
    p_de.set_defaults(fn=destroy)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
```

The templates it fills in:
Create **`cli/templates/main.py.tpl`**:

```text
"""__NAME__ — scaffolded by the tamani golden path (__GOLDEN_VERSION__).

Ships on day one with: split health probes, JSON logs with correlation
ids, Prometheus metrics, hardening, network policy, monitoring, alerts,
signed supply chain and a runbook stub. Replace the sample endpoint with
your logic; the operability stays.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

SERVICE_NAME = "__NAME__"
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

app = FastAPI(title=SERVICE_NAME)


@app.middleware("http")
async def correlation(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
    correlation_id.set(cid)
    response = await call_next(request)
    response.headers["x-correlation-id"] = cid
    return response


@app.get("/health/live")
def liveness():
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/ready")
def readiness():
    # Add real dependency checks here (database, queue, downstream service).
    return {"status": "ok"}


@app.get("/hello")
def hello():
    log.info("hello served")
    return {"service": SERVICE_NAME, "message": "scaffolded and serving"}


Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

Create **`cli/templates/Dockerfile.tpl`**:

```text
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY main.py .
USER 10001
EXPOSE __PORT__
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "__PORT__"]
```

Create **`cli/templates/requirements.txt.tpl`**:

```text
fastapi==0.115.12
uvicorn[standard]==0.34.0
prometheus-fastapi-instrumentator==7.0.2
```

Create **`cli/templates/k8s.yaml.tpl`**:

```text
# __NAME__ — generated by the tamani golden path __GOLDEN_VERSION__.
# Correctness by default: a service scaffolded this way cannot ship
# without probes, limits, telemetry, network policy and monitoring.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: __NAME__
  namespace: tamani-dev
automountServiceAccountToken: false
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: __NAME__
  namespace: tamani-dev
  labels: { app: __NAME__, golden-path: "__GOLDEN_VERSION__" }
spec:
  replicas: 1
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 0, maxUnavailable: 1 }
  selector:
    matchLabels: { app: __NAME__ }
  template:
    metadata:
      labels: { app: __NAME__ }
    spec:
      serviceAccountName: __NAME__
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: app
          image: ghcr.io/maicymxtim/__NAME__:main
          imagePullPolicy: Always
          ports: [{ containerPort: __PORT__ }]
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
          resources:
            requests: { cpu: 50m, memory: 96Mi }
            limits: { cpu: 250m, memory: 192Mi }
          startupProbe:
            httpGet: { path: /health/live, port: __PORT__ }
            failureThreshold: 30
            periodSeconds: 2
          readinessProbe:
            httpGet: { path: /health/ready, port: __PORT__ }
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /health/live, port: __PORT__ }
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: __NAME__
  namespace: tamani-dev
  labels: { app: __NAME__ }
spec:
  selector: { app: __NAME__ }
  ports: [{ port: 80, targetPort: __PORT__ }]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: __NAME__
  namespace: tamani-dev
spec:
  podSelector:
    matchLabels: { app: __NAME__ }
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector: {}
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
      ports:
        - port: __PORT__
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: __NAME__
  namespace: tamani-dev
spec:
  selector:
    matchLabels: { app: __NAME__ }
  endpoints:
    - targetPort: __PORT__
      path: /metrics
      interval: 30s
---
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: __NAME__-slo
  namespace: tamani-dev
spec:
  groups:
    - name: __NAME__.alerts
      rules:
        - alert: __ALERTNAME__HighErrorRate
          expr: |
            (sum(rate(http_requests_total{namespace="tamani-dev", handler!="/metrics", status=~"5..", job="__NAME__"}[5m])) or vector(0))
            / clamp_min(sum(rate(http_requests_total{namespace="tamani-dev", job="__NAME__"}[5m])), 1e-9) > 0.05
          for: 10m
          labels: { severity: warning, namespace: tamani-dev }
          annotations:
            summary: "__NAME__ error rate above 5%"
            runbook: runbooks/__NAME__.md
```

Create **`cli/templates/ci.yml.tpl`**:

```text
name: svc-__NAME__

on:
  push:
    branches: [main]
    paths: ["apps/__NAME__/**"]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        id: build
        with:
          context: apps/__NAME__
          push: true
          tags: |
            ghcr.io/maicymxtim/__NAME__:${{ github.sha }}
            ghcr.io/maicymxtim/__NAME__:main
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: trivy vulnerability scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/maicymxtim/__NAME__:${{ github.sha }}
          severity: CRITICAL
          ignore-unfixed: true
          exit-code: "1"
      - name: sbom
        uses: anchore/sbom-action@v0.17.8
        with:
          image: ghcr.io/maicymxtim/__NAME__:${{ github.sha }}
          artifact-name: sbom-__NAME__.spdx.json
      - uses: sigstore/cosign-installer@v3.7.0
      - run: cosign sign --yes ghcr.io/maicymxtim/__NAME__@${{ steps.build.outputs.digest }}
```

Create **`cli/templates/argo-app.yaml.tpl`**:

```text
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: svc-__NAME__
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:MaicyMxtim/tamani-platform.git
    targetRevision: main
    path: platform/k8s/services/__NAME__
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    retry:
      limit: 5
      backoff: { duration: 30s, factor: 2 }
```

Create **`cli/templates/runbook.md.tpl`**:

```text
# __NAME__

**Owner:** __OWNER__
**Scaffolded:** __DATE__ (golden path __GOLDEN_VERSION__)

**What it does:** <one sentence — fill this in before first incident>

**First three checks:**
1. `kubectl -n tamani-dev get pods -l app=__NAME__`
2. `kubectl -n tamani-dev logs deploy/__NAME__ --tail=50`
3. Grafana → filter metrics by `job="__NAME__"`

**Dependencies:** <list them; then add them to the NetworkPolicy>

**Escalation:** fix in Git, never live. Argo CD owns this service.
```

Create **`cli/templates/catalogue.yaml.tpl`**:

```text
name: __NAME__
owner: __OWNER__
scaffolded: "__DATE__"
golden_path: "__GOLDEN_VERSION__"
runbook: runbooks/__NAME__.md
namespace: tamani-dev
port: __PORT__
dependencies: []
```


```bash
chmod +x cli/tamani
./cli/tamani new example-api --port 8000
git add -A && git commit -m 'scaffold example-api' && git push
```

**Check:** The scaffolded service reaches live traffic with no manual cluster command, admitted through the same signature policy as every other workload.

---

# Phase 11 — Cost and unit economics

This phase puts a measured money figure on the system, focusing on the cost that dominates an AI product.

## Unit economics and cost attribution

Unit economics express cost per unit of value, such as per thousand classifications. Cost attribution assigns spending to namespaces, workloads or purposes. For an AI product, inference spending dominates compute, so it is the primary line to measure.

## Model tiering and the self-hosting crossover

Model tiering routes easy work to a cheaper model and hard work to an expensive one, with the accuracy cost measured rather than assumed. The self-hosting crossover is the volume at which running one's own model becomes cheaper than a managed provider, found by comparing per-token pricing against a machine's hourly cost and throughput.

## The experiment

Runs the golden set through each candidate model and reports accuracy and cost per model, so the accuracy cost of tiering is measured.

Create **`evals/tiering_experiment.py`**:

```python
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
```


```bash
python3 evals/tiering_experiment.py
```

Read the cost per thousand classifications from the gateway's `/v1/costs` endpoint, compute the self-hosting crossover, and record the figures with their methods.

**Check:** Cost per thousand classifications is known; the tiering table shows accuracy and cost per model; the self-hosting crossover is computed and compared to the real workload volume.

---

# Completion

The platform is complete when the site serves over HTTPS from the cluster, deployed only through the repository; the evaluation gate guards accuracy; unsigned images are refused; the secret lives in a managed store; and the reliability, cost and self-service evidence is recorded. Every concept above has a definition and a purpose, and every file has its full contents and the reason it exists.

