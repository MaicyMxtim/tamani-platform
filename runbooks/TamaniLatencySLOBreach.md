# TamaniLatencySLOBreach

**Symptom:** p95 latency above 400ms for 15 minutes.

**First three checks:**
1. Grafana: is request rate up (load) or flat (regression)?
2. `kubectl -n tamani-prod top pods` — CPU throttling near limits?
3. Loki: slow-request logs; check correlation ids of slow paths.

**Common causes:** CPU limits too low after a traffic rise, a slow
dependency call on the hot path, node swap pressure.

**Escalation:** raise replica count or CPU limits via Git if load-driven;
otherwise treat as a regression and bisect recent promotions.
