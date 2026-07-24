# Platform Engineering — a study reference

A subject-by-subject reference for the concepts used to build the Tamani Platform. Each chapter defines a concept, explains why it is used, lists its key terminology, describes how it works, gives best practices, and records how it was implemented in this project.

---

# 1. APIs

An API (Application Programming Interface) is a defined way for one piece of software to request data or actions from another over a network. A web API receives structured requests over HTTP and returns structured responses, usually as JSON.

## Purpose

An API separates a service's capabilities from the clients that use them. A mobile app, a website and another backend can all call the same API without sharing code, and the service can change internally as long as the API contract stays stable.

## Terminology

- **Endpoint** — a single URL path that performs one operation, such as `/venues`.
- **HTTP method** — the verb describing intent: `GET` reads, `POST` creates, `PUT`/`PATCH` update, `DELETE` removes.
- **Status code** — a number describing the outcome: `2xx` success, `4xx` client error, `5xx` server error.
- **JSON** — the standard text format for request and response bodies.
- **Contract** — the agreed set of endpoints, inputs and outputs a client can rely on.

## Mechanics

A client sends an HTTP request to an endpoint. The server processes it, performs any work, and returns a status code and a response body. The exchange is stateless: each request carries everything the server needs, and the server keeps no memory of previous requests unless it stores state elsewhere.

## Best practices

- Give endpoints clear, resource-oriented names.
- Use the correct HTTP method and status code for each operation.
- Validate all input at the boundary.
- Version the API so changes do not break existing clients.
- Return errors that state what went wrong.

## In the Tamani Platform

The venue API is written with FastAPI, a Python framework for building web APIs. It exposes read endpoints for venue search, a public feed, and health checks. Data is served from a bundled snapshot of 1,275 venues, or from a database when one is configured.

---

# 2. Docker

A container packages an application together with everything it needs to run: the runtime, libraries and system dependencies. This ensures the application behaves the same on a developer's machine, a test environment and production. Docker is the standard platform for building and running containers.

## Purpose

Without containers, software often behaves differently across machines because of differing versions of runtimes, libraries and configuration. Containers eliminate this by shipping a fixed environment alongside the code.

## Terminology

- **Image** — a read-only package containing an application and all of its dependencies.
- **Container** — a running instance of an image.
- **Dockerfile** — a text file containing the instructions used to build an image.
- **Layer** — a cached step in an image build; reused when unchanged to speed rebuilds.
- **Registry** — a store for images, such as GitHub Container Registry.

## Mechanics

A Dockerfile lists build steps. Building it produces an image. Running the image produces a container, isolated from the host and other containers but sharing the host kernel. Images are pushed to a registry and pulled wherever they are needed.

## Best practices

- Use multi-stage builds so build tools are discarded from the final image.
- Run as a non-root user.
- Keep images small by choosing slim base images.
- Use a read-only root filesystem where possible.
- Include health check endpoints.
- Pin exact image versions rather than mutable tags such as `latest`.

## In the Tamani Platform

Each service has a multi-stage Dockerfile that installs dependencies in a builder stage and copies only the result into a slim final image. Containers run as a non-root user with a read-only root filesystem and dropped Linux capabilities. Final images are kept under 200 MB.

---

# 3. Docker Compose

Docker Compose runs multiple containers together as a single application, defined in one configuration file.

## Purpose

Real systems consist of several services (an application, a database, a cache, a message broker). Compose starts them together with one command, giving a reproducible local environment.

## Terminology

- **Service** — one container definition within a Compose file.
- **compose.yml** — the file describing services, their images, ports and dependencies.
- **Volume** — persistent storage that outlives a container.
- **Depends-on** — an ordering hint between services.

## Mechanics

The Compose file declares each service, its build source or image, environment variables, ports and volumes. One command builds and starts the whole set on a shared network where services reach each other by name.

## Best practices

- Keep the Compose file as the single description of the local stack.
- Use named volumes for data that must persist.
- Mirror production configuration where practical.
- Expose only the ports needed for local work.

## In the Tamani Platform

A Compose file runs the API, the inference gateway, a worker, Redis, NATS, Postgres, Prometheus and Grafana together for local development. A Makefile wraps common operations (`up`, `down`, `test`, `smoke`) as single commands.

---

# 4. Kubernetes

Kubernetes is a system that runs and manages containers across one or more machines. It is given a declarative description of the desired state and continuously works to make the actual state match it.

## Purpose

Running containers by hand does not scale: containers must be restarted on failure, replaced on new versions, spread across machines and connected to each other. Kubernetes automates this.

## Terminology

- **Cluster** — a set of machines managed together by Kubernetes.
- **Node** — one machine in the cluster.
- **Pod** — the smallest deployable unit, usually one container.
- **Deployment** — a controller that keeps a specified number of identical pods running and manages rollouts.
- **Service** — a stable internal name and address for a set of pods.
- **Namespace** — a partition within a cluster used to separate environments or teams.
- **kubectl** — the command-line tool for interacting with a cluster.
- **Manifest** — a YAML file declaring a desired resource.

## Mechanics

Desired state is submitted as manifests. Controllers compare desired state against actual state and take corrective action: creating pods, replacing failed ones, and rolling out new versions gradually. Scheduling places pods onto nodes based on available resources and constraints.

## Best practices

- Set resource requests and limits on every container.
- Separate environments with namespaces.
- Use liveness, readiness and startup probes that test distinct conditions.
- Apply Pod Security standards to block privileged workloads.
- Use PodDisruptionBudgets to preserve availability during disruptions.

## In the Tamani Platform

The platform runs on minikube locally and on k3s on a single cloud node. Three namespaces separate development, staging and production. Workloads declare resource requests and limits, three distinct health probes, and restricted Pod Security. A PodDisruptionBudget keeps at least one API replica available during voluntary disruptions.

---

# 5. Networking

Networking in Kubernetes governs how pods communicate with each other, with services inside the cluster, and with the outside world.

## Purpose

By default every pod can reach every other pod. Controlling this traffic limits the blast radius of a compromise and enforces that services only talk to their declared dependencies. Ingress controls how external traffic reaches the cluster.

## Terminology

- **NetworkPolicy** — a rule set defining which pods may send or receive traffic.
- **Default deny** — a baseline policy that blocks all traffic until specific paths are allowed.
- **DNS** — the service that resolves names (such as `redis`) to addresses; provided in-cluster by CoreDNS.
- **Ingress** — a rule mapping external hostnames and paths to internal services.
- **Ingress controller** — the component that implements ingress rules, such as ingress-nginx.
- **TLS** — encryption for traffic in transit, providing the padlock in HTTPS.

## Mechanics

NetworkPolicies select pods by label and permit named ingress and egress paths; anything not permitted is dropped. External traffic reaches an ingress controller, which terminates TLS and routes requests to the correct service based on hostname and path. Certificates for TLS are issued and renewed automatically by a certificate manager.

## Best practices

- Start from default-deny and open only required paths.
- Explicitly allow DNS egress, since default-deny blocks it and breaks all name resolution.
- Terminate TLS at the edge and redirect HTTP to HTTPS.
- Rate-limit at the edge as a first line of defence.
- Restrict which single workload may make outbound calls to external providers.

## In the Tamani Platform

A default-deny NetworkPolicy blocks all pod traffic; explicit policies open only the required paths, with DNS egress allowed separately. ingress-nginx terminates TLS for `platform.waypear.com`, using certificates issued automatically by cert-manager from Let's Encrypt. Only the inference gateway is permitted outbound HTTPS to the model provider.

---

# 6. Storage

Storage covers how applications hold data, both transient (in memory or a cache) and durable (surviving restarts).

## Purpose

Containers are ephemeral: their local filesystem is lost when they stop. Data that must persist, or must be shared between replicas, requires storage that lives independently of any single container.

## Terminology

- **Volume** — storage attached to a pod.
- **PersistentVolumeClaim** — a request for durable storage of a given size.
- **emptyDir** — a temporary volume that exists only for a pod's lifetime.
- **Cache** — fast, often in-memory storage for data that can be recomputed.
- **Object store** — remote storage for files, such as AWS S3.

## Mechanics

Stateless services keep no local durable data and can be replaced freely. Stateful components attach volumes. In-memory stores such as Redis serve caches and counters at high speed but lose data on restart unless configured to persist. Object storage holds files and backups outside the cluster.

## Best practices

- Keep services stateless where possible.
- Document and test backup and restore procedures.
- Use caches for data that can be regenerated, not as a system of record.
- Never cache results produced by a fallback path, so that a degraded answer is not served after recovery.

## In the Tamani Platform

Redis provides the job queue, the semantic cache and the rate-limiter backend. Application services are stateless and serve read traffic from a bundled snapshot. Backups are stored in an S3 bucket with a lifecycle rule that expires old objects.

---

# 7. Infrastructure as Code

Infrastructure as Code (IaC) defines cloud infrastructure in text files that are applied by tooling, rather than configured by hand in a console.

## Purpose

Manual infrastructure is not reproducible, has no history, and drifts from any documentation. IaC makes infrastructure version-controlled, reviewable and rebuildable.

## Terminology

- **Provider** — the plugin that lets IaC manage a given platform, such as AWS.
- **Resource** — one managed infrastructure object, such as a virtual machine.
- **State** — the tool's record of what it has created.
- **Plan** — a preview of the changes an apply would make.
- **Drift** — divergence between the real infrastructure and its written definition.

## Mechanics

Resources are declared in configuration files. The tool compares the configuration against its state and the real infrastructure, produces a plan, and on apply creates, updates or deletes resources to match. Re-running a plan against unchanged configuration reports no changes, confirming zero drift.

## Best practices

- Keep configuration in version control.
- Store state remotely and lock it during operations.
- Review the plan before every apply.
- Keep secret values out of configuration and state.

## In the Tamani Platform

Infrastructure is defined with OpenTofu (an open-source fork of Terraform): a single cloud node, an elastic IP, a DNS zone, a backup bucket and a scoped IAM identity. A drift check after apply reports no changes. Secret values are never placed in configuration or state.

---

# 8. AWS

Amazon Web Services (AWS) is a cloud provider that rents computing, storage, networking and managed services on demand.

## Purpose

Renting infrastructure removes the need to own hardware, allows scaling up and down, and provides managed services (DNS, storage, secret stores) that would otherwise require operating dedicated software.

## Terminology

- **EC2** — virtual machine instances.
- **Elastic IP** — a fixed public address that can be reassigned.
- **Route 53** — the DNS service.
- **S3** — object storage.
- **SSM Parameter Store** — a store for configuration values and secrets.
- **IAM** — the identity and access-management system controlling who can do what.
- **Security group** — a firewall attached to an instance.

## Mechanics

Resources are provisioned in a region. Access is governed by IAM identities and policies that grant least-privilege permissions. A security group restricts which ports are reachable and from where. Managed services such as DNS and secret storage are consumed through their APIs rather than run directly.

## Best practices

- Grant least-privilege IAM permissions scoped to specific resources.
- Restrict administrative ports to known addresses.
- Use managed services for DNS, storage and secrets rather than self-hosting.
- Keep credentials out of source control.

## In the Tamani Platform

A single EC2 instance in the London region runs the cluster, fronted by an elastic IP. Route 53 hosts the DNS zone for the domain. S3 stores backups. SSM Parameter Store holds the model provider key. A dedicated IAM identity has read-only access limited to that one parameter path. The security group restricts SSH and the cluster API to a known address.

---

# 9. CI/CD

Continuous Integration and Continuous Delivery (CI/CD) automate testing, building and packaging of software on every change.

## Purpose

Manual build and test steps are slow and inconsistent. Automating them on every push catches regressions early and produces trusted, repeatable build artifacts.

## Terminology

- **Pipeline** — the automated sequence of steps run on a change.
- **Workflow / job / step** — the units of a pipeline.
- **Runner** — the machine that executes the pipeline.
- **Artifact** — an output of the pipeline, such as a container image.
- **Gate** — a check that must pass before the pipeline proceeds.

## Mechanics

A change to the repository triggers the pipeline. It runs tests, and on success builds and pushes container images to a registry. Additional steps can scan for vulnerabilities, generate a software bill of materials, sign the image and check for leaked secrets. A failing gate stops the pipeline.

## Best practices

- Run the full test suite on every change.
- Build once and promote the same artifact through environments.
- Fail the build on critical vulnerabilities, with an explicit, time-limited exception process.
- Scan for committed secrets.
- Sign artifacts so their origin can be verified.

## In the Tamani Platform

GitHub Actions runs the tests, then builds and pushes images to GitHub Container Registry. The pipeline scans images with Trivy and fails on fixable critical vulnerabilities, generates an SBOM with Syft, signs images with Cosign, and scans the repository history for secrets with Gitleaks. A separate evaluation gate scores AI classifier changes against a golden set and blocks regressions.

---

# 10. GitOps

GitOps is a delivery model in which the Git repository is the single source of truth for the desired state of a system, and software continuously reconciles the running system to match it.

## Purpose

Deploying by running commands against a cluster is error-prone and undocumented. GitOps makes every change a commit, gives deployments a full history, and makes recovery a matter of pointing the reconciler back at the repository.

## Terminology

- **Reconciliation** — the continuous process of making actual state match declared state.
- **App-of-apps** — a pattern where one root application defines all others.
- **Sync wave** — an ordering mechanism for dependent resources.
- **Automated vs manual sync** — whether changes apply immediately or require human approval.
- **Image pinning** — deploying an exact image version identified by commit or digest.

## Mechanics

A reconciler running in the cluster watches the repository. When the repository changes, it applies the difference to the cluster. Environments can differ in trust: development can sync automatically, while production requires a deliberate human sync. Pinning images by commit identifier makes the running version precisely known.

## Best practices

- Make the repository the only way to change the cluster.
- Require manual approval for production promotion.
- Pin production images by exact version.
- Order dependent resources with sync waves.
- Verify the deployed artifact, not only the reconciler's status.

## In the Tamani Platform

Argo CD runs in the cluster and reconciles it from the repository using a read-only deploy key. An app-of-apps root application defines all others. Platform configuration syncs automatically; production workloads require a manual sync. Production images are pinned by commit SHA.

---

# 11. Observability

Observability is the ability to understand a system's internal state from its external outputs: metrics, logs and traces. Service Level Objectives (SLOs) express reliability targets against those signals.

## Purpose

A running system fails in ways that are invisible without measurement. Observability makes failures detectable, diagnosable and quantifiable, and SLOs turn "is it healthy" into a measurable target.

## Terminology

- **Metric** — a numeric measurement over time, such as requests per second.
- **Log** — a timestamped record of an event.
- **Trace** — the path of a single request across services.
- **SLI** — a Service Level Indicator; a measured ratio of good events to valid events.
- **SLO** — a Service Level Objective; a target for an SLI, such as 99.5% availability.
- **Error budget** — the allowed amount of failure implied by an SLO.
- **Burn rate** — how fast the error budget is being consumed.

## Mechanics

Services expose metrics that a collector scrapes on a schedule. Logs are shipped to a central store and queried by correlation identifier. SLIs are computed from metrics with recording rules. Alerts fire when the error budget burns too fast: a fast burn pages immediately, a slow burn raises a ticket. Dashboards present the results by audience.

## Best practices

- Define SLIs as a ratio of good events to valid events.
- Alert on error-budget burn rate, using multiple windows to reduce noise.
- Attach a correlation identifier to every request and log line.
- Split dashboards by audience: service health, spend, and so on.
- Watch metric cardinality; high-cardinality labels can exhaust the metrics store.

## In the Tamani Platform

Prometheus scrapes application and platform metrics; Loki stores logs; Grafana presents dashboards. SLOs define 99.5% availability and 95% of requests under 400 milliseconds. Recording rules compute the error ratio, and multi-window burn-rate alerts page on fast burns and ticket on slow burns. Two dashboards separate service health from AI spend.

---

# 12. Messaging

A message system moves work between services asynchronously through durable queues, rather than through direct synchronous calls.

## Purpose

Work that does not need an immediate answer should not block a request. A queue lets a producer hand off work and a consumer process it at its own pace, and lets work wait safely when consumers are unavailable.

## Terminology

- **Stream** — a durable, ordered log of messages.
- **Subject** — a message's address, often hierarchical.
- **Consumer** — a reader's position in a stream.
- **Consumer group** — multiple workers sharing one stream, each message going to one member.
- **At-least-once delivery** — the guarantee that a message is delivered one or more times.
- **Idempotency** — the property that processing the same message twice has no additional effect.
- **Dead letter queue** — a place for messages that repeatedly fail.
- **Poison message** — a malformed message that crashes consumers if retried.
- **Consumer lag** — the number of unprocessed messages.

## Mechanics

Producers publish messages to subjects on a durable stream. A consumer group shares the stream so each message is handled once. A worker acknowledges a message only after completing the work; an unacknowledged message is redelivered. Failed messages are retried with growing delays and moved to a dead letter queue after a limit. Malformed messages are quarantined immediately. Consumer lag can drive autoscaling.

## Best practices

- Acknowledge only after work completes, so a crash redelivers rather than loses work.
- Make every consumer idempotent, using an idempotency key written after success.
- Retry with exponential backoff and cap redelivery.
- Quarantine poison messages instead of retrying them.
- Configure retention by age and size to bound stream growth.
- Use consumer lag, not CPU, as the autoscaling signal for worker pools.

## In the Tamani Platform

NATS JetStream carries enrichment events on a hierarchical subject scheme. Workers form a durable consumer group, acknowledge after completion, and use idempotency keys written only on success. Failures retry with exponential backoff and dead-letter after five deliveries; malformed messages are quarantined. Retention is bounded by age and size, and a replay tool can reprocess from any sequence.

---

# 13. AI Gateway

An inference gateway is a single service that owns every call to a language-model provider, adding access control, caching, cost accounting and fallback around it.

## Purpose

Calling a provider directly from application code scatters keys, spending and behaviour across the system. Routing all calls through one gateway centralises control and makes cost and reliability measurable and enforceable.

## Terminology

- **Inference** — obtaining a result from a trained model.
- **Structured output** — constraining a model to return data matching a schema.
- **Semantic cache** — a cache keyed by meaning, using embeddings and similarity, rather than exact match.
- **Embedding** — a numeric vector representing the meaning of text.
- **Token budget** — a per-caller limit on token spend.
- **Circuit breaker** — a mechanism that stops calling a failing dependency and falls back.
- **Prompt versioning** — treating each prompt as a versioned artifact.

## Mechanics

A request passes through tenant authentication, a token-budget check, and a semantic-cache lookup. If a stored answer is similar enough, it is returned without a provider call. Otherwise the provider is called with structured output enforced, the result is cached and recorded in a cost ledger, and returned. A circuit breaker falls back to a cheap local result if the provider is unhealthy.

## Best practices

- Keep provider keys out of application code; concentrate them in the gateway.
- Enforce structured output so responses are valid by construction.
- Tune the semantic-cache threshold against real data, measuring false-hit rate.
- Enforce per-tenant budgets rather than only observing spend.
- Version prompts and record the version on every result.
- Never cache fallback output.

## In the Tamani Platform

The gateway calls the model provider through the official SDK with structured output. A semantic cache uses locally-computed embeddings; the similarity threshold was set to 0.94 after measuring hit and false-hit rates across 400 venues. Per-tenant token budgets return a rate-limit response when exhausted. A circuit breaker falls back to a deterministic classifier. Prompts are versioned artifacts, and every request is written to a cost ledger.

---

# 14. Security

Security here covers admission control, image signing, vulnerability scanning, and secret management: ensuring only trusted, scanned, signed workloads run, and that secrets are never exposed.

## Purpose

A cluster that runs any image, or holds secrets in plain files, is exposed to supply-chain attacks and leaks. Enforcing provenance and centralising secrets reduces this risk.

## Terminology

- **Admission controller** — a component that inspects and can reject resources before they run.
- **Policy** — a rule the admission controller enforces.
- **Image signing** — attaching a verifiable signature proving an image's origin.
- **Keyless signing** — signing tied to a workflow identity rather than a stored key.
- **SBOM** — a Software Bill of Materials listing an image's contents.
- **Secret store** — a managed system holding secret values outside the cluster and Git.

## Mechanics

An admission controller evaluates every resource against policies and rejects violations: unsigned images, missing resource limits, dangerous privileges. Images are signed during the build using a workflow identity, and the cluster verifies the signature before admitting them. Secrets live in a managed store and are synced into the cluster by an operator, never committed to Git.

## Best practices

- Reject unsigned images and images with mutable tags.
- Require resource limits and forbid privileged containers at admission.
- Sign images with a workflow identity rather than a long-lived key.
- Scan images and generate an SBOM in the pipeline.
- Store secrets in a managed store and sync them in with least-privilege access.

## In the Tamani Platform

Kyverno enforces admission policies: pinned image tags, required resource limits, required labels, and verified signatures for images from the project registry. CI signs images with Cosign using GitHub's workflow identity; the cluster rejects unsigned images, verified by attempting to run one. External Secrets Operator syncs the provider key from SSM Parameter Store using a read-only identity.

---

# 15. Reliability

Reliability engineering proves and improves a system's behaviour under load and failure, through load testing, chaos experiments and blameless postmortems.

## Purpose

A system's limits and failure modes are unknown until tested. Deliberately loading and breaking it under controlled conditions reveals its saturation point and confirms whether its safety mechanisms work.

## Terminology

- **Load test** — driving controlled traffic to measure capacity and latency.
- **Saturation point** — the load at which a resource is exhausted.
- **Limiting resource** — the resource that saturates first.
- **Chaos experiment** — a deliberate fault injected with a stated hypothesis.
- **Postmortem** — a blameless write-up of an incident and its lessons.
- **Runbook** — a documented procedure for responding to an alert.

## Mechanics

Load tests raise traffic in stages while measuring latency and error rate, identifying the saturation point and the limiting resource. Chaos experiments state a hypothesis, inject a fault (killing a pod, adding latency), and record the result against the hypothesis. Incidents are written up as postmortems focused on why the system permitted the failure, and each alert gains a runbook.

## Best practices

- State a hypothesis before each experiment and record the result against it.
- Identify the limiting resource, not only the breaking point.
- Write blameless postmortems that fix the class of failure, not only the symptom.
- Maintain a runbook for every alert that can fire.
- Encode corrective actions as code so they persist.

## In the Tamani Platform

Load testing with k6 found a saturation point around 25–30 concurrent users, limited by memory because the whole platform shares one small node. Chaos experiments confirmed that killing an API replica caused no user-visible errors, and that killing the single-replica gateway caused a 20-second automatic-recovery gap. Three incidents were written up as blameless postmortems, and each alert has a runbook.

---

# 16. Platform Engineering Practices

Platform engineering practices are the disciplines that make a platform maintainable and trustworthy: documented decisions, versioned configuration, and standardised operability.

## Purpose

A platform without recorded reasoning, versioned configuration and consistent standards becomes unmaintainable as it grows and as knowledge is lost.

## Terminology

- **ADR** — an Architecture Decision Record documenting a significant choice.
- **Monorepo** — a single repository holding application code, infrastructure and configuration.
- **Golden path** — the supported, standardised way to build and run a service.
- **Service catalogue** — a record of every service, its owner, dependencies and runbook.

## Mechanics

Significant decisions are recorded as ADRs stating context, options, decision and consequences. Application code, infrastructure and configuration live together in a monorepo so a single change can span them. A golden path defines the standard way to create a service, and a catalogue records ownership and metadata for each.

## Best practices

- Record significant decisions as ADRs at the time they are made.
- Keep application, infrastructure and configuration in one repository where practical.
- Standardise service creation through a golden path.
- Maintain a catalogue of services and their owners.

## In the Tamani Platform

A monorepo holds applications, infrastructure, platform configuration, evaluations, runbooks, the CLI and documentation. ADRs record decisions such as choosing NATS over Kafka and running a single-node cluster. A service catalogue entry is generated for each scaffolded service.

---

# 17. Developer Self-Service

Developer self-service provides a tool that scaffolds and deploys a fully operable service without requiring the developer to know cluster internals.

## Purpose

If each new service must be wired for probes, metrics, policy, security and monitoring by hand, services ship inconsistently and often without operability. A generator makes correctness the default.

## Terminology

- **Scaffolding** — generating a complete service from a template.
- **Template** — the parameterised source for generated files.
- **Correctness by default** — the property that generated services are operable without extra work.
- **Time to first deploy** — the elapsed time from scaffold to serving traffic.

## Mechanics

A command takes a service name and generates every file the service needs: a hardened container definition, health endpoints, metrics, a network policy, a monitoring configuration, an alert, a signed build pipeline, a deployment manifest and a runbook. Committing and pushing the result causes the GitOps reconciler to deploy it. Because the template supplies operability, a service cannot ship without it.

## Best practices

- Generate the full operable set, not just application code.
- Make the generated pipeline sign and scan images like every other service.
- Version the templates so upgrades can be applied across services.
- Measure and record time to first deploy.

## In the Tamani Platform

A CLI scaffolds a service with a hardened Dockerfile, split probes, structured logging, metrics, a network policy, a service monitor, an error-rate alert, a signed CI pipeline, an Argo application, a catalogue entry and a runbook. A scaffolded service went from command to serving live traffic in a measured 195 seconds, and its signed image was admitted through the same signature policy as every other workload.

---

# 18. Cost Optimisation

Cost optimisation measures and reduces the running cost of a system, with particular attention to inference spend in an AI-backed product.

## Purpose

Without measurement, the cost of a feature is unknown and cannot be controlled. For an AI product, inference dominates cost long before compute does, so it is the primary line to measure and reduce.

## Terminology

- **Unit economics** — cost expressed per unit of value, such as per thousand classifications.
- **Cost attribution** — assigning cost to namespaces, workloads or purposes.
- **Model tiering** — routing easy work to a cheaper model and hard work to an expensive one.
- **Crossover point** — the volume at which self-hosting becomes cheaper than a managed provider.
- **Caching savings** — spend avoided by serving cached results.

## Mechanics

Each request is recorded with its model, tokens, cost and cache status, allowing cost per unit to be computed. Tiering is evaluated by measuring accuracy and cost per model on a fixed test set, then routing by confidence. The self-hosting crossover is found by comparing per-token provider pricing against the hourly cost and throughput of a self-hosted alternative.

## Best practices

- Treat inference as the primary cost line for an AI product.
- Price input and output tokens separately.
- State cache savings as money.
- Measure the accuracy cost of model tiering rather than assuming it.
- Compute the self-hosting crossover before deciding to self-host.

## In the Tamani Platform

A cost ledger records every request. Measured cost is about 4.01 US dollars per thousand classifications after caching, with a 22% cache saving on early traffic. A tiering experiment measured F1 and cost per model (Haiku, Sonnet, Opus) on the golden set; confidence-based routing is projected to cut blended cost by about 57% for a small accuracy loss. The self-hosting crossover sits far above the workload's volume, so the managed provider is cheaper.

---

*This reference documents the concepts used in the Tamani Platform. Implementation detail lives in the repository: `docs/adr/` for decisions, `runbooks/` for operations and incidents, and `docs/unit-economics.md` for cost figures.*
