# Tamani Platform Walkthrough

A guided tour of what the Tamani Platform is, how it is built, and where each part lives. For the underlying concepts, see the study reference (`docs/study-reference.md`). For decisions, incidents and cost, see `docs/adr/`, `runbooks/` and `docs/unit-economics.md`.

---

## Overview

The Tamani Platform runs a venue-discovery backend as a production-grade internal platform. It takes a real workload — 1,275 Brighton venues — and builds the infrastructure that a platform, cloud, DevOps or SRE team would run around it: a Kubernetes platform delivered by GitOps, a governed AI inference gateway, autonomous agents kept safe by a governance layer, full observability, an enforced secure supply chain, reliability evidence, a developer self-service tool, and published unit economics.

It is deployed live and reachable on the public internet.

## Live endpoints

- **Landing:** https://platform.waypear.com/
- **Interactive API explorer:** https://platform.waypear.com/docs
- **Venue search:** https://platform.waypear.com/venues?vibe=late-night
- **Ranked feed:** https://platform.waypear.com/feed?limit=10

The site runs on a single cloud node; under heavy load or during a deploy it can exhaust memory and briefly go offline, which is documented behaviour rather than a fault (see `runbooks/postmortems/` and `runbooks/chaos/`).

## Architecture

The system is organised in tiers.

- **Edge** — ingress-nginx terminates TLS for `platform.waypear.com` using certificates issued automatically by cert-manager, and applies a first-line rate limit.
- **Application** — the venue API (FastAPI) serves search and the public feed; the inference gateway owns every call to the language-model provider; a worker pool consumes background jobs.
- **Agent** — an enrichment agent classifies venues; an operations agent triages alerts. Both run under a shared governance runtime.
- **Messaging** — NATS JetStream carries asynchronous events between services; nothing calls another service synchronously for work that can wait.
- **Data** — Redis provides the job queue, the semantic cache and the rate-limiter backend; a bundled snapshot serves venue reads.
- **Platform** — k3s on one cloud node, reconciled from Git by Argo CD, observed by Prometheus, Grafana and Loki, with admission policy enforced by Kyverno and secrets supplied by External Secrets Operator.

## Repository layout

- **`apps/`** — the services: `api`, `gateway`, `worker`, and the `agents` (enrichment and ops, sharing `governance.py`).
- **`infra/terraform/`** — the cloud node, DNS, backup bucket and IAM identity as code.
- **`platform/`** — the GitOps content: Argo CD app-of-apps definitions (`argocd/`), Kubernetes manifests (`k8s/`), admission policies (`policies/`).
- **`evals/`** — the golden set, the scoring harness, the CI gate, the tiering experiment.
- **`runbooks/`** — one file per alert, plus the postmortem and chaos archives.
- **`cli/`** — the `tamani` platform CLI and its golden-path templates.
- **`docs/`** — architecture decision records, the study reference, this walkthrough, and the unit-economics report.

## Request paths

**A venue search** enters at the edge, is routed to the API service, and is answered from the bundled snapshot. No AI call is involved, so a search costs effectively nothing.

**A venue enrichment** begins as a message on `venue.enrichment.requested`. A worker consumes it and calls the gateway, which checks the caller's token budget, looks in the semantic cache, and only on a miss calls the provider with structured output enforced. The result is cached and recorded in a cost ledger. Low-confidence results are routed to a human review queue rather than written as fact.

**An alert** is handed to the operations agent, which inspects the cluster with a read-only identity, retrieves the matching runbook, asks the gateway for a diagnosis grounded in the collected evidence, and opens a pull request containing the diagnosis and a proposed remediation. It never applies a change directly.

## Component tour

**Venue API** (`apps/api`) — FastAPI service with split liveness, readiness and startup probes, structured JSON logging with a correlation identifier, and Prometheus metrics.

**Inference gateway** (`apps/gateway`) — the only service holding the provider key. It enforces per-tenant token budgets, a semantic cache tuned to a 0.94 similarity threshold, structured output, a circuit breaker with a deterministic fallback, prompt versioning, and a per-request cost ledger.

**Worker** (`apps/worker`) — a durable NATS consumer with idempotency keys, explicit acknowledgement after completion, exponential-backoff retries, a dead-letter subject, poison-message quarantine, and a replay tool.

**Agents** (`apps/agents`) — the enrichment and operations agents run under a governance runtime that enforces a capability manifest, token and time and tool-call budgets, loop detection, a dry-run mode, and per-call tracing. The operations agent additionally holds a read-only Kubernetes identity with no write verbs.

## Delivery

Every change flows through Git. GitHub Actions runs tests, then builds, scans, generates an SBOM for, and signs each image. Argo CD reconciles the cluster from the repository: platform configuration syncs automatically, while production workloads require a deliberate manual sync and are pinned to an exact commit. The cluster rejects any image that is not signed by the project's CI.

## Operations

**Observability** — Prometheus scrapes metrics, Loki stores logs, Grafana presents a service-health dashboard and an AI-spend dashboard. Service Level Objectives define 99.5% availability and a 400-millisecond latency target, with multi-window burn-rate alerts.

**Security** — Kyverno enforces signed images, pinned tags, resource limits and non-privileged workloads at admission. The provider key lives in AWS Parameter Store and is synced in by External Secrets Operator with a read-only identity.

**Reliability** — load and chaos experiments established the platform's saturation point and confirmed its recovery behaviour; three blameless postmortems and a per-alert runbook set record what has failed and how it was handled.

## Developer self-service

The `tamani` CLI scaffolds a complete, operable service from one command: a hardened container, health probes, metrics, a network policy, a monitoring configuration and alert, a signed CI pipeline, an Argo application, a catalogue entry and a runbook. A scaffolded service reached live traffic in a measured 195 seconds, admitted through the same signature policy as every other workload.

## Measured results

- Availability and latency against the SLOs: 100% and 95 milliseconds p95 in the measured window.
- Cost per thousand classifications: about $4.01 after caching, with a 22% cache saving on early traffic.
- Model tiering: routing by confidence is projected to cut blended cost by about 57% for a small, measured accuracy loss.
- Golden-set accuracy: 80.3% precision, 68.0% recall, enforced as a CI regression gate.
- Time from scaffold command to serving traffic: 195 seconds.
- Saturation point: around 25–30 concurrent users, limited by node memory.

## How it maps to roles

- **Cloud Support / SRE** — the incident diagnosis, postmortems, SLOs and burn-rate alerting.
- **DevOps / Platform Engineer** — GitOps delivery, admission policy, the golden path and self-service CLI.
- **AI Platform Engineer** — the governed gateway economics and the evaluation gate blocking a regressing prompt.

---

*The repository is the primary artifact; every figure above is measured and reproducible from it.*
