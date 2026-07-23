# reviews-api

**Owner:** maicy
**Scaffolded:** 2026-07-23 (golden path gp-1.0.0)

**What it does:** <one sentence — fill this in before first incident>

**First three checks:**
1. `kubectl -n tamani-dev get pods -l app=reviews-api`
2. `kubectl -n tamani-dev logs deploy/reviews-api --tail=50`
3. Grafana → filter metrics by `job="reviews-api"`

**Dependencies:** <list them; then add them to the NetworkPolicy>

**Escalation:** fix in Git, never live. Argo CD owns this service.
