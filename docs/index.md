# Tamani Platform

A production-grade internal platform running a venue-discovery backend on Kubernetes, delivered entirely by GitOps, with a governed AI inference gateway, autonomous agents kept safe by a governance layer, full observability, a secure supply chain, reliability evidence, a developer self-service tool, and published unit economics.

## Live

- **Platform:** [platform.waypear.com](https://platform.waypear.com/)
- **Interactive API explorer:** [platform.waypear.com/docs](https://platform.waypear.com/docs)
- **Source:** [github.com/MaicyMxtim/tamani-platform](https://github.com/MaicyMxtim/tamani-platform)

## Read

- **[Walkthrough](walkthrough.html)** — a tour of the finished platform: architecture, components and measured results.
- **[Complete Guide](complete-guide.html)** — every concept explained for a beginner, then the platform built from an empty directory with every file and the reason for each.
- **[Unit economics](unit-economics.html)** — the measured cost figures and their methods.

## Measured results

- Availability 100% and p95 latency 95 ms against the service level objectives in the measured window.
- Cost per thousand classifications: about $4.01 after caching.
- Model tiering projected to cut blended cost by about 57% for a small, measured accuracy loss.
- Golden-set accuracy: 80.3% precision, 68.0% recall, enforced as a CI regression gate.
- Time from a single scaffold command to a service serving live traffic: 195 seconds.
- Saturation point around 25–30 concurrent users, limited by node memory.

## How it maps to roles

- **Cloud Support / SRE** — incident diagnosis, postmortems, service level objectives, burn-rate alerting.
- **DevOps / Platform Engineer** — GitOps delivery, admission policy, the golden path and self-service CLI.
- **AI Platform Engineer** — the governed gateway economics and the evaluation gate blocking a regressing prompt.
