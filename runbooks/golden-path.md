# The golden path

`tamani new <name>` scaffolds a service that is operable on the day it is
created. Measured once (reviews-api, 2026-07-23): **195 seconds from the
scaffold command to the service answering traffic in dev** — 161s of that
was CI building, scanning, generating an SBOM and signing the image; the
rest was Argo CD reconciling and the pod passing its probes. No cluster
commands were run by hand.

The generated output covers, per the project plan:
- a Dockerfile following the hardening standard (non-root, read-only
  root, dropped capabilities, multi-stage)
- liveness, readiness and startup endpoints
- Prometheus metrics wired
- a CI pipeline with vulnerability scanning, SBOM and cosign signing
- an Argo CD application manifest
- a NetworkPolicy scoped to declared dependencies
- resource requests and limits
- a ServiceMonitor and a default error-rate alert
- a runbook stub linked to that alert
- a service catalogue entry

Correctness by default: a developer on the golden path cannot ship a
service without probes, telemetry, policy, a signed supply chain and a
runbook, because the template supplies them. The image is signed by the
generated CI and admitted only because it passes the cluster's signature
policy — the same gate that protects every other workload.
