# Postmortem: production node memory exhaustion during rolling deploy

**Date:** 2026-07-23 · **Duration:** ~10 minutes of full outage · **Severity:** SEV-1 (public API down)

## Timeline (UTC)
- 00:29 — Phase 4 promotion synced: prod pinned to new image sha, rolling
  deploy begins. Node must hold old + new pods simultaneously while
  pulling three fresh images.
- 00:31 — kubectl reports intermittent `TLS handshake timeout`; sync
  completes and reports Healthy/Synced.
- 00:33 — Public API stops responding on 443. Kubernetes API times out.
  SSH accepts TCP connections but cannot execute commands: the node is
  thrashing, not dead.
- 00:36 — Decision: reboot via `aws ec2 reboot-instances` (all state is
  in Git; workload data is reproducible).
- 00:38 — Node back, k3s activating, memory at 488 MiB used of 1907.
- 00:39 — 2 GiB swapfile added and persisted in /etc/fstab.
- 00:42 — All 5 prod pods Running on the new image; public API serving.

## Impact
platform.waypear.com fully down ~10 minutes. No data loss: stream and
cache are reproducible, source of truth is Git.

## Root cause
A t3.small (2 GiB) node running k3s, Argo CD, ingress-nginx,
cert-manager and 5 workload pods sits near its memory ceiling at steady
state. A rolling deploy doubles workload pod memory transiently
(maxSurge default) while containerd unpacks three new images —
page-cache pressure plus new allocations pushed the node into swapless
thrash: unable to OOM-kill fast enough to stay schedulable.

## Contributing factors
- No swap: every allocation failure became reclaim-thrash, not a kill.
- Rolling update surge on a single node doubles footprint by design.
- No memory alerts existed yet (observability is Phase 7) — the first
  signal was a user-visible outage.

## Corrective actions
- [x] 2 GiB swapfile on the node, persisted, and added to the Terraform
  user_data so a rebuilt node has it from first boot.
- [x] Rolling update strategy for prod set to maxSurge 0 / maxUnavailable 1
  — brief per-service blip instead of node-wide collapse on a 1-node cluster.
- [ ] Node memory/pressure alerting when Prometheus lands (Phase 7).
- [ ] Upgrade to t3.medium (4 GiB) before the observability stack deploys.

## Lessons
The sync status said Healthy while the node was dying: control-plane
health is not workload health. Also, the cheapest mitigation (swap)
is worth doing before the first incident, not after.
