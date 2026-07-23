# KubePodNotReady

**Symptom:** a pod has been in a non-ready state (Pending, ImagePullBackOff,
CrashLoopBackOff, Error) for longer than the alert window.

**First three checks:**
1. `kubectl -n <ns> get pods` — which pod, which state, how many restarts.
2. `kubectl -n <ns> describe pod <pod>` — read Events at the bottom:
   image pull errors name the bad reference; scheduling failures name the
   unsatisfiable constraint; OOMKilled appears in last state.
3. `kubectl -n <ns> logs <pod> --previous` — the crash reason if the
   container starts and dies.

**Common causes:** a typo'd or unpushed image tag (ImagePullBackOff), a
failing readiness dependency, quota exhaustion (Pending with no node
assigned), a bad config or secret reference, OOMKilled from a limit set
too low.

**Escalation:** if the pod is managed by Argo CD, fix the manifest in Git
rather than editing live. Page a human if user-facing traffic is failing;
the ops agent must only propose changes by pull request.
