# Postmortem: second memory exhaustion — same signature, one size up

**Date:** 2026-07-23 · **Duration:** ~15 minutes public API outage · **Severity:** SEV-1

## Timeline (UTC)
- 16:3x — Phase 8 additions deploy: Kyverno admission controller and
  External Secrets Operator join a node already at ~3.1/3.8 GiB, while a
  rolling deploy pulls three freshly signed images.
- 16:5x — kubectl calls time out; public API down; SSH shows 3.6/3.8 GiB
  used and swap 100% full with load 4.5: thrashing, the Phase 4
  signature exactly.
- 17:0x — Reboot via AWS; gateway cut from 2 replicas to 1 in Git before
  the reboot so the resync applies the lighter footprint.
- 17:1x — Recovered: 3.0/3.8 GiB with swap easing. A post-reboot sync
  applied a stale revision (second occurrence of the Argo stale-revision
  gotcha); a hard refresh + resync converged the cluster on the signed
  images.

## Root cause
Aggregate memory limits exceed physical memory. Each addition was
individually reasonable; nobody added up the column. The largest single
consumer was the second gateway replica (embedding model ≈ 400 MiB per
replica) providing little value on a single-node cluster.

## Corrective actions
- [x] Gateway to 1 replica (the embedding model is the platform's most
  expensive process after Prometheus).
- [x] Kyverno deployed admission-only: background, reports and cleanup
  controllers disabled.
- [ ] Memory-pressure alert (node above 85% for 10m) — the alert
  existed conceptually in Phase 7 but was not yet written. Do it.
- [ ] Before any new component lands: sum the requests column and check
  it against the node. A one-line make target could print this.

## Lessons
Same failure twice means the first postmortem fixed symptoms, not the
class. The class is "no admission control on memory commitments" — the
platform now reviews aggregate limits before each component lands, the
same way it reviews code.
