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
