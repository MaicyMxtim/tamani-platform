# Tamani Platform

An agentic infrastructure project: the Tamani venue discovery backend run as a
production-grade internal platform on Kubernetes, delivered by GitOps, with a
governed inference gateway and agentic workloads under evaluation gates.

Live at **https://platform.waypear.com**. Full plan and evidence in `docs/`.
All twelve phases complete; every headline number is measured, not claimed.

| Phase | Status | Evidence |
|---|---|---|
| 0. Foundation & repo | done | Terraform on AWS, zero-drift check |
| 1. Containerisation | done | multi-stage, non-root, images under 200 MB |
| 2. Kubernetes platform | done | tenancy, RBAC, default-deny netpol, Kyverno |
| 3. GitOps delivery | done | Argo app-of-apps, manual prod gate, sha pinning |
| 4. Event backbone | done | NATS delivery semantics, all failure modes proven |
| 5. Inference gateway | done | real Opus, semantic cache, quotas, ~$4/1k live |
| 6. Governed agents | done | manifest/budget/loop/dry-run; ops agent opened PR #1 |
| 7. Observability & SLOs | done | Prometheus/Grafana/Loki, burn-rate alerts |
| 8. Security & supply chain | done | cosign signing enforced, Trivy, SBOM, ESO |
| 9. Reliability proof | done | 3 postmortems, chaos with stated hypotheses |
| 10. Developer self-service | done | `tamani new` → serving in 195s, measured |
| 11. Cost & unit economics | done | tiering experiment, crossover, $/1k published |

Documentation:
- **`docs/walkthrough.md`** — a tour of the finished platform.
- **`docs/build-guide.md`** — step-by-step reproduction from an empty machine.
- **`docs/study-reference.md`** — the underlying concepts, subject by subject.

Evidence: `docs/unit-economics.md`, `runbooks/postmortems/`,
`runbooks/chaos/`, `runbooks/golden-path.md`, `docs/adr/`.

## Repository layout

```
apps/       API service, inference gateway, workers, agents
infra/      Terraform for the cloud node, DNS, registry, storage
platform/   Argo CD app-of-apps, Kustomize overlays, admission policies
evals/      golden set, scoring harness, historical results
runbooks/   one file per alert, plus the postmortem archive
cli/        the platform command line tool
docs/       architecture decision records
ops/        local prometheus + grafana config for docker compose
```

## Run it from a clean machine

Prerequisites: Docker Desktop.

```
make up      # build and start the full local stack
make smoke   # verify every service answers
make test    # unit tests
make down    # stop
```

Services once up:

- API: http://localhost:8000 (venues, feed, /docs)
- Inference gateway: http://localhost:8001 (needs `x-api-key: dev-local-key`)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- NATS monitoring: http://localhost:8222
