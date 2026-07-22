"""
Tamani enrichment worker — consumes venue.enrichment.requested from NATS
JetStream and calls the gateway to classify.

Phase 1 scope: durable consumer, explicit ack after completion, idempotency
key check in Redis. Phase 4 adds backoff, max-delivery dead-lettering and
poison quarantine; Phase 6 replaces the direct call with the agent loop.
"""
import asyncio
import json
import logging
import os
import sys
import time

import httpx
import nats
from nats.js.api import ConsumerConfig, DeliverPolicy

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

STREAM = "VENUE"
SUBJECT_REQUESTED = "venue.enrichment.requested"
SUBJECT_COMPLETED = "venue.enrichment.completed"
SUBJECT_FAILED = "venue.enrichment.failed"


def already_done(r, idempotency_key: str) -> bool:
    return not r.set(f"idem:{idempotency_key}", int(time.time()), nx=True, ex=86400)


async def handle(msg, js, r):
    payload = json.loads(msg.data)
    idem = payload.get("idempotency_key") or f"venue-{payload['venue_id']}"
    if already_done(r, idem):
        log.info("duplicate delivery for %s, acking without work", idem)
        await msg.ack()
        return
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GATEWAY_URL}/v1/classify",
                json={"venue_id": payload["venue_id"],
                      "description": payload["description"]},
                headers={"x-api-key": GATEWAY_KEY},
            )
            resp.raise_for_status()
        await js.publish(SUBJECT_COMPLETED, resp.content)
        await msg.ack()  # explicit ack only after the work is complete
        log.info("enriched venue %s", payload["venue_id"])
    except Exception as exc:  # noqa: BLE001
        # release the idempotency claim so a redelivery can retry
        r.delete(f"idem:{idem}")
        log.error("enrichment failed for %s: %s", payload.get("venue_id"), exc)
        await js.publish(SUBJECT_FAILED, json.dumps(
            {"venue_id": payload.get("venue_id"), "error": str(exc)}
        ).encode())
        await msg.nak(delay=5)


async def main():
    import redis
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    try:
        await js.add_stream(name=STREAM, subjects=["venue.enrichment.*"])
    except Exception:  # noqa: BLE001 - stream already exists
        pass
    sub = await js.subscribe(
        SUBJECT_REQUESTED,
        durable="enrichment-workers",
        queue="enrichment-workers",
        config=ConsumerConfig(deliver_policy=DeliverPolicy.ALL, max_deliver=5),
        manual_ack=True,
    )
    log.info("worker consuming %s", SUBJECT_REQUESTED)
    async for msg in sub.messages:
        await handle(msg, js, r)


if __name__ == "__main__":
    asyncio.run(main())
