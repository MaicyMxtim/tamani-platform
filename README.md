# Tamani Platform

An agentic infrastructure project: the Tamani venue discovery backend run as a
production-grade internal platform on Kubernetes, delivered by GitOps, with a
governed inference gateway and agentic workloads under evaluation gates.

The full plan lives in `docs/`. Build status by phase:

| Phase | Status |
|---|---|
| 0. Foundation and repository structure | in progress |
| 1. Containerisation and the workload | in progress |
| 2–11 | not started |

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
