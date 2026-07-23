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
