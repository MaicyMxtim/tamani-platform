## Symptom
Pod `tamani-dev/demo-broken` has been not ready for 5+ minutes. `kubectl get pods` shows it as `0/1` with status `ImagePullBackOff` (0 restarts, age 20s), meaning the container has never started.

## Root cause (cite specific evidence lines)
The pod cannot pull its container image because the image reference does not exist in the registry. Specific evidence:
- Spec references image: `ghcr.io/maicymxtim/tamani-api:does-not-exist`
- Events: `Failed to pull image "ghcr.io/maicymxtim/tamani-api:does-not-exist": rpc error: code = NotFound desc = ... failed to resolve reference ... : not found`
- Events: `Error: ErrImagePull` followed by `Back-off pulling image`

This is a `NotFound` error (not an auth/`401` error), which matches the runbook's "typo'd or unpushed image tag (ImagePullBackOff)" common cause. The tag literally reads `does-not-exist`, strongly suggesting a bad/placeholder image tag rather than a registry credential problem.

## Proposed remediation (the change a human should review and apply)
Correct the image tag in the pod/workload manifest to a real, pushed tag of `ghcr.io/maicymxtim/tamani-api` (e.g. a valid version/SHA). Steps for the reviewer:
1. Confirm the intended tag exists in GHCR.
2. Update the `image:` field in the source manifest (do **not** edit the live object) — if this workload is managed by Argo CD, make the change in Git and open a pull request per the runbook.
3. Let the deployment roll out and confirm the pod reaches `1/1 Ready`.

## Confidence (high/medium/low, one sentence why)
**High** — the describe Events give an explicit `NotFound`/`not found` error naming the exact unresolvable image reference, which unambiguously identifies the bad image tag as the cause.

---
*Opened autonomously by the ops agent. A human must review and apply any remediation.*
