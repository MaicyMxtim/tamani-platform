# TamaniErrorBudgetFastBurn

**Symptom:** the API is failing enough requests to spend over 2% of the
monthly error budget per hour. Users are seeing errors right now.

**First three checks:**
1. Grafana "Tamani — Service Health": which status codes are rising?
2. `kubectl -n tamani-prod get pods` — restarts or not-ready pods?
3. Loki: filter `{namespace="tamani-prod"}` for level=ERROR around onset.

**Common causes:** a bad deploy (check Argo CD history, roll back by
reverting the Git pin), a dependency outage (Redis, provider), node
memory pressure (check the memory panel).

**Escalation:** revert the last promotion commit first, ask questions
after. The ops agent may already have opened a PR with a diagnosis.
