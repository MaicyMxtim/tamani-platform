# __NAME__

**Owner:** __OWNER__
**Scaffolded:** __DATE__ (golden path __GOLDEN_VERSION__)

**What it does:** <one sentence — fill this in before first incident>

**First three checks:**
1. `kubectl -n tamani-dev get pods -l app=__NAME__`
2. `kubectl -n tamani-dev logs deploy/__NAME__ --tail=50`
3. Grafana → filter metrics by `job="__NAME__"`

**Dependencies:** <list them; then add them to the NetworkPolicy>

**Escalation:** fix in Git, never live. Argo CD owns this service.
