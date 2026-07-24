# Tamani Platform — Build Guide

A step-by-step guide to reproducing the platform from an empty machine. Each step gives the command to run, an explanation of what it does and why, and a check to confirm it worked before moving on. The repository is the reference implementation: file contents live in the repo, and this guide is the order and reasoning for assembling them.

Work through it in sequence. Do not skip verification steps; each one confirms the previous work before the next depends on it.

---

## How to use this guide

The build has two tracks:

- **Local track** (Phases 0–2, 4–6, and the evaluation work) runs entirely on your own machine with Docker and minikube. Anyone can complete it end to end at no cost.
- **Cloud track** (Phases 3, 7–11 in production) requires your own AWS account, a domain you control, and a language-model provider API key. The steps are identical to what produced the live system, but the account, domain and key are yours to supply.

Throughout, `REPO` means the root of the cloned repository.

## Prerequisites

Install these tools. On macOS, `brew install <name>` for each unless noted.

- **git** and a **GitHub account** — version control and image hosting.
- **Docker Desktop** — builds and runs containers.
- **minikube** and **kubectl** — a local Kubernetes cluster and its CLI.
- **helm** — installs third-party Kubernetes charts.
- **OpenTofu** (`brew install opentofu`, command `tofu`) — infrastructure as code; a free Terraform fork.
- **k6** — load testing.
- **gh** — the GitHub CLI, authenticated with `gh auth login`.

Cloud track additionally:

- **AWS CLI** (`aws configure` with an IAM access key), an **AWS account**, a **domain**, and a **provider API key**.

Clone the repository as your reference:

```bash
git clone https://github.com/MaicyMxtim/tamani-platform.git
cd tamani-platform
```

---

## Phase 0 — Foundation

**Goal:** a monorepo and the infrastructure definitions, with a reproducible command surface.

1. **Understand the layout.** The repository is a monorepo: `apps/` holds services, `infra/` holds Terraform, `platform/` holds Kubernetes and GitOps content, `evals/`, `runbooks/`, `cli/` and `docs/` hold the rest. Keeping everything together lets one commit span code and infrastructure.

2. **Read the Makefile** (`REPO/Makefile`). It exposes every common operation as a single verb: `make up`, `make down`, `make test`, `make smoke`. This is what makes the workflow reproducible from a clean machine.

3. **Read the Terraform** (`REPO/infra/terraform/`). It declares one cloud node, an elastic IP, a DNS zone, a backup bucket and a scoped IAM identity. Do not apply it yet — that is the cloud track in Phase 3.

**Check:** `ls apps infra platform evals runbooks cli docs` lists all seven top-level directories.

---

## Phase 1 — Containerisation

**Goal:** each service packaged as a hardened container, and the whole stack running locally.

1. **Read a service and its Dockerfile.** Open `apps/api/main.py` and `apps/api/Dockerfile`. The Dockerfile uses a **multi-stage build**: dependencies are installed in a builder stage, and only the result is copied into a slim final image, so build tools are not shipped. The final stage adds a non-root user, a read-only root filesystem and dropped capabilities.

2. **Note the health probes.** The API exposes `/health/live`, `/health/ready` and `/health/startup`. These answer different questions: liveness tests only that the process responds, readiness tests that dependencies are reachable, startup covers the boot window. Configuring them identically is a common mistake.

3. **Start the full stack:**

   ```bash
   make up
   ```

   This runs `docker compose up --build -d`, building the images and starting the API, gateway, worker, Redis, NATS, Postgres, Prometheus and Grafana on a shared network.

4. **Smoke-test it:**

   ```bash
   make smoke
   ```

**Check:** the smoke test returns `ok` from the health endpoints and a classification from the gateway. `docker compose ps` shows every service `Up`.

---

## Phase 2 — Kubernetes platform

**Goal:** a multi-tenant cluster with isolation, quotas, RBAC, network policy and admission control, proven with negative tests.

1. **Start a local cluster with a real network plugin:**

   ```bash
   minikube start --cni=calico --memory=6g --cpus=4
   ```

   Calico is required because minikube's default plugin silently ignores NetworkPolicy. Without it, the network tests in step 7 would pass for the wrong reason.

2. **Create the namespaces and tenancy** (`platform/k8s/tenancy/`):

   ```bash
   kubectl apply -f platform/k8s/tenancy/
   ```

   This creates the dev, staging and prod namespaces with restricted Pod Security, a ResourceQuota and LimitRange per namespace, and the developer and deployer RBAC roles.

3. **Build the images inside the cluster's Docker and deploy the dev overlay:**

   ```bash
   eval $(minikube docker-env)
   docker build -t tamani-api:dev apps/api
   docker build -t tamani-gateway:dev apps/gateway
   docker build -t tamani-worker:dev apps/worker
   kubectl apply -k platform/k8s/overlays/dev
   ```

4. **Install the admission controller:**

   ```bash
   helm repo add kyverno https://kyverno.github.io/kyverno/
   helm install kyverno kyverno/kyverno -n kyverno --create-namespace --wait
   kubectl apply -f platform/policies/baseline.yaml
   ```

5. **Prove RBAC is scoped:**

   ```bash
   kubectl auth can-i get pods -n tamani-dev --as=jane --as-group=tamani:developers   # yes
   kubectl auth can-i delete deployments -n tamani-dev --as=jane --as-group=tamani:developers   # no
   ```

6. **Prove admission control rejects a bad image:**

   ```bash
   kubectl -n tamani-dev run bad --image=nginx:latest
   ```

   This is refused: the policy forbids the `latest` tag.

7. **Prove network policy denies by default.** Exec into the API pod and try to reach the gateway; the connection is refused because only the worker's path to the gateway is allowed.

**Check:** RBAC returns `yes` then `no`; the `latest`-tag pod is refused at admission; the disallowed network path fails while the allowed one succeeds.

---

## Phase 3 — Cloud infrastructure and GitOps *(cloud track)*

**Goal:** the platform running on a real node, reconciled from Git.

1. **Provision the cloud node.** Supply your admin IP and SSH public key in `infra/terraform/terraform.tfvars` (kept out of Git), then:

   ```bash
   cd infra/terraform && tofu init && tofu plan -out=tfplan
   tofu apply tfplan
   ```

   Review the plan before applying. It creates the EC2 node, elastic IP, DNS zone, backup bucket and IAM identity. The outputs include four nameservers.

2. **Delegate DNS.** Set those four nameservers at your domain registrar. This points your domain at AWS's DNS.

3. **Confirm zero drift:**

   ```bash
   tofu plan   # expect: No changes
   ```

   A clean plan proves the live infrastructure matches the definition.

4. **Fetch the cluster credentials** from the node and confirm `kubectl get nodes` works remotely.

5. **Install Argo CD** with Helm, register the repository with a read-only deploy key, and apply the single root application (`platform/argocd/root.yaml`). From here, the cluster reconciles itself from Git: platform configuration syncs automatically, production workloads require a manual sync.

6. **Add the edge.** The GitOps content deploys ingress-nginx and cert-manager, a Let's Encrypt issuer and an ingress for your domain. TLS is issued automatically.

**Check:** `tofu plan` reports no changes; Argo CD shows the applications Synced and Healthy; your domain serves over HTTPS.

---

## Phase 4 — Event backbone

**Goal:** asynchronous work with correct delivery semantics, each failure mode demonstrated.

1. **Read the worker** (`apps/worker/main.py`). It is a durable NATS consumer that acknowledges only after completing work, writes an idempotency key on success, retries with exponential backoff, dead-letters after a delivery limit, and quarantines malformed messages.

2. **Demonstrate poison-message quarantine.** Publish invalid data to the request subject and confirm the worker parks it in the quarantine subject and continues.

3. **Demonstrate dead-lettering.** Publish a message that always fails and confirm it is retried with growing delays, then moved to the dead-letter subject after the fifth attempt.

4. **Demonstrate redelivery.** Kill a worker mid-message and confirm a healthy worker completes it, proving no work is lost.

5. **Demonstrate replay.** Run `apps/worker/replay.py --from-seq 1 --dry-run` and confirm it walks the stream from a chosen point.

**Check:** garbage is quarantined without crashing the pool; a hopeless message dead-letters after five tries with visible backoff; a killed worker's message is completed by another.

---

## Phase 5 — Inference gateway

**Goal:** a single governed door to the model provider, with caching, budgets and measured cost.

1. **Provide the provider key locally.** Put it in `REPO/.env` (gitignored):

   ```bash
   echo 'ANTHROPIC_API_KEY=sk-ant-YOUR-KEY' > .env
   ```

2. **Read the gateway** (`apps/gateway/`). The request path is: tenant authentication, token-budget check, semantic-cache lookup, provider call with structured output, cache store, cost ledger. `provider.py` holds the circuit breaker and fallback; `semcache.py` holds the embedding cache; `budget.py` holds the quotas.

3. **Rebuild and test live:**

   ```bash
   make up
   curl -s -X POST http://localhost:8001/v1/classify \
     -H 'x-api-key: dev-local-key' -H 'content-type: application/json' \
     -d '{"venue_id":"t1","description":"late night cocktail bar"}'
   ```

   Send a near-duplicate description and confirm the second returns `"cached": true`.

4. **Tune the cache threshold** against real data:

   ```bash
   docker compose exec gateway python /tmp/tune.py   # see evals/tune_threshold.py
   ```

   The threshold was set to 0.94 because that produced zero false hits on the sample.

5. **Read the cost ledger:**

   ```bash
   curl -s http://localhost:8001/v1/costs -H 'x-api-key: dev-local-key'
   ```

**Check:** the first classification calls the provider and reports a real cost; the near-duplicate is served from cache at zero cost; `/v1/costs` reports spend and cache savings.

---

## Phase 6 — Golden set, evaluation, and governed agents

**Goal:** a measured accuracy baseline enforced in CI, and two agents kept safe by a governance runtime.

1. **Build the golden set.** Open `tools/labeler.html` in a browser, label the venues, and export `golden_set.jsonl` into `evals/`. This is the human-judged yardstick.

2. **Score the classifier:**

   ```bash
   EVAL_KEY=mobile-local-key python3 evals/run_eval.py
   ```

   Record the precision and recall as the baseline (`evals/baseline.json`).

3. **Add the CI gate.** `.github/workflows/eval.yml` runs the golden set on any gateway change; `evals/check_gate.py` fails the build if accuracy regresses beyond tolerance.

4. **Read the governance runtime** (`apps/agents/governance.py`). It enforces a capability manifest (only declared tools may run), token, time and tool-call budgets, loop detection, a dry-run mode, and per-call tracing.

5. **Run the enrichment agent** and prove the controls:

   ```bash
   python apps/agents/enrichment/agent.py --venue <id>            # real run
   python apps/agents/enrichment/agent.py --venue <id> --dry-run  # side effects simulated
   python apps/agents/enrichment/demo_violations.py               # each violation refused
   ```

6. **Run the operations agent against a broken pod.** Deploy a pod with a nonexistent image tag, then run `apps/agents/ops/agent.py --alert alert.json`. It investigates read-only, diagnoses the cause, and opens a pull request. It cannot change the cluster.

**Check:** the eval gate blocks a regressing prompt; an undeclared tool, a budget breach and a loop are each refused; the ops agent opens a correct pull request without write access.

---

## Phase 7 — Observability and SLOs *(cloud track)*

**Goal:** metrics, logs, reliability targets and burn-rate alerts.

1. **Deploy the monitoring stack** via GitOps (`platform/argocd/apps/monitoring.yaml`, `loki.yaml`). These install kube-prometheus-stack and Loki with values trimmed for a small node.

2. **Expose the services to Prometheus.** Add the ServiceMonitors and a network policy allowing the monitoring namespace to scrape (`platform/k8s/slo/`). Services must carry an `app` label for the ServiceMonitor selector to match.

3. **Define the SLOs.** `platform/k8s/slo/slo-rules.yaml` holds recording rules and multi-window burn-rate alerts for 99.5% availability and a 400 ms latency target.

4. **Add the dashboards** (`platform/k8s/slo/dashboards.yaml`), loaded by Grafana's sidecar.

5. **Verify scraping and rules:**

   ```bash
   kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9095:9090
   # then query up{namespace="tamani-prod"} and tamani:api_error_ratio:rate5m
   ```

**Check:** Prometheus lists the tamani targets as `up`; the SLO recording rules return values; the Grafana dashboards render availability, latency and spend.

---

## Phase 8 — Security and supply chain *(cloud track)*

**Goal:** only signed, scanned images run, and secrets live outside Git.

1. **Harden CI** (`.github/workflows/ci.yml`): sign images with Cosign using GitHub's workflow identity, scan with Trivy and fail on fixable criticals, generate an SBOM with Syft, and scan history with Gitleaks.

2. **Enforce signatures.** Deploy Kyverno on the cloud cluster and apply `platform/policies/verify-images.yaml`, which requires a valid keyless signature for images from your registry.

3. **Prove enforcement:**

   ```bash
   kubectl -n tamani-prod run unsigned --image=ghcr.io/<you>/tamani-api:<old-unsigned-sha>
   ```

   This is refused: `no signatures found`.

4. **Move the secret out of the cluster.** Put the key in AWS Parameter Store, provision a read-only IAM identity (`infra/terraform/eso.tf`), and deploy External Secrets Operator with an ExternalSecret (`platform/k8s/secrets/`). It syncs the key in hourly.

**Check:** an unsigned image is refused at admission; a signed image is admitted; the cluster secret's content matches the value in Parameter Store.

---

## Phase 9 — Reliability proof *(cloud track)*

**Goal:** the platform's limits and failure behaviour, measured and recorded.

1. **Load test:**

   ```bash
   BASE_URL=https://<your-domain> VUS_LOW=5 VUS_HIGH=30 k6 run tools/load/api-load.js
   ```

   Raise the load until a resource saturates. Record the saturation point and which resource limits first.

2. **Add a PodDisruptionBudget** for the API (`platform/k8s/base/api/pdb.yaml`) so a replica always survives disruption.

3. **Chaos, with a written hypothesis first.** Under light load, kill an API replica and confirm zero user-visible errors. Kill the single-replica gateway and time the classification outage and automatic recovery.

4. **Write it up.** Record each experiment's hypothesis and result in `runbooks/chaos/`, and any incident in `runbooks/postmortems/`, focused on why the system permitted the failure.

**Check:** the load test names the saturation point and limiting resource; the API pod kill causes no errors; the gateway kill recovers on its own; the results are written up.

---

## Phase 10 — Developer self-service

**Goal:** one command that scaffolds a fully operable, signed service.

1. **Read the CLI and templates** (`cli/tamani`, `cli/templates/`). The templates emit a hardened container, health probes, metrics, a network policy, a monitoring configuration and alert, a signed CI pipeline, an Argo application, a catalogue entry and a runbook.

2. **Scaffold a service and time it:**

   ```bash
   ./cli/tamani new example-api --port 8000
   git add -A && git commit -m "scaffold example-api" && git push
   ```

   CI builds and signs the image; Argo CD deploys it. Measure the elapsed time from the scaffold command to the service answering traffic.

3. **List the catalogue:**

   ```bash
   ./cli/tamani catalogue
   ```

**Check:** the scaffolded service reaches live traffic without any manual cluster command, admitted through the same signature policy as every other workload.

---

## Phase 11 — Cost and unit economics

**Goal:** a real money figure per unit of work, and the tiering and self-hosting analysis.

1. **Read the cost figures** from the ledger endpoint (`/v1/costs`): cost per thousand classifications, gross and after cache.

2. **Run the tiering experiment:**

   ```bash
   # inside the gateway container, which has the SDK and provider.py
   python3 evals/tiering_experiment.py
   ```

   This runs the golden set through each candidate model and reports accuracy and cost per model, so the accuracy cost of routing cheap-vs-expensive is measured, not assumed.

3. **Compute the crossover** between the managed provider and self-hosting, using per-token pricing against a self-hosted GPU's hourly cost and throughput.

4. **Write it up** in `docs/unit-economics.md`, stating each figure's method.

**Check:** cost per thousand classifications is known; the tiering table shows accuracy and cost per model; the self-hosting crossover is computed and compared to the workload's real volume.

---

## After the build

The platform is complete when: the site serves over HTTPS from your cluster, deployed only through Git; the eval gate guards accuracy; unsigned images are refused; the secret lives in a managed store; and the reliability, cost and self-service evidence is recorded. The repository is the artifact; every figure in the evidence documents is reproducible by the steps above.

For the concepts behind each step, read `docs/study-reference.md`. For a tour of the finished system, read `docs/walkthrough.md`.
