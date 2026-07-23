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
