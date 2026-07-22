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
