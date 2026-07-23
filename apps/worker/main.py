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
