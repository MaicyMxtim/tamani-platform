# Chaos and load experiments — 2026-07-23

Each experiment states its hypothesis before execution and records the
result against it, per the project plan.

## Load: saturation point of the single-node platform

**Hypothesis:** the public edge serves clean traffic below its 20 rps
per-IP rate limit; total platform capacity lands well above realistic
Brighton-venue-browsing load.

**Result: hypothesis partially rejected — and the rejection is the
finding.** At roughly 25–30 concurrent external users, the node (which
runs the control plane, the full monitoring stack and the workloads)
entered swap thrash and dropped off the network entirely; kubectl and
the public API both went dark, requiring a reboot (the day's third
memory incident). The saturation point of the *platform* is far lower
than the capacity of the *API*, because everything shares 4 GiB.

**Limiting resource: memory** — load drives page-cache pressure, swap
fills, and the machine becomes catatonic rather than slow.

**Corrective directions (recorded, deliberately not all applied):**
separate control plane from workloads (a second small node), move the
monitoring stack off-node, front the read-only API with a CDN cache, or
buy a bigger machine. On a portfolio budget the honest documentation of
the ceiling is worth more than the fix.

## C1: API pod killed under live traffic

**Hypothesis:** with two replicas, readiness gates and a
PodDisruptionBudget, killing one API pod causes zero user-visible
errors.

**Result: confirmed.** 1,787 requests during the window, **0 failed**,
p95 54 ms. The replacement pod was Running before the run ended.

## C2: single-replica gateway killed

**Hypothesis:** the gateway (deliberately single-replica after
postmortem #2 — its embedding model costs ~400 MiB per replica) is a
known single point of failure for classification; killing it causes a
15–40 s classification outage while the venue API is unaffected;
recovery is automatic.

**Result: confirmed.** Classification unavailable for **20 seconds**,
recovery fully automatic, venue API untouched. The queue-based design
means enrichment work waits rather than fails: NATS redelivers to the
worker once the gateway returns.

## Not executed

- **Node drain** — meaningless on a one-node cluster; recorded as a
  known limitation rather than pantomimed.
- **Provider latency injection** — the circuit breaker and mock
  fallback path were already proven live in Phase 5 (the misconfigured
  key incident exercised exactly this path in production).
