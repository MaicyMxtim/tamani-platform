# Tamani Platform

A production platform running a venue discovery backend on Kubernetes. It serves a public API, routes every AI call through a governed gateway, runs two autonomous agents inside a safety layer, and enforces a signed supply chain. It is deployed on a cloud server and reachable on the internet.

## Live

| What | Where |
|---|---|
| Platform | [platform.waypear.com](https://platform.waypear.com/) |
| API explorer | [platform.waypear.com/docs](https://platform.waypear.com/docs) |
| Source | [github.com/MaicyMxtim/tamani-platform](https://github.com/MaicyMxtim/tamani-platform) |

## Contents

1. [Walkthrough](walkthrough.html). A tour of the finished platform: architecture, components and results.
2. [Costs](unit-economics.html). The measured cost figures and how they were arrived at.

## Stack

| Layer | Tool |
|---|---|
| Cloud | AWS EC2, Route53, S3 |
| Infrastructure as code | OpenTofu |
| Cluster | k3s |
| Deployment | Argo CD |
| Edge | ingress-nginx, cert-manager |
| Services | FastAPI |
| Messaging | NATS JetStream |
| Data | Redis |
| AI gateway | Anthropic API, semantic cache |
| Monitoring | Prometheus, Grafana, Loki |
| Supply chain | cosign, trivy, syft, gitleaks, Kyverno |
| Secrets | External Secrets Operator, AWS SSM |

## Results

| Measure | Value |
|---|---|
| Availability in the measured window | 100% |
| p95 latency | 95 ms |
| Cost per thousand classifications | about $4.01 after caching |
| Saving projected from model tiering | about 57% |
| Classification precision | 80.3% |
| Classification recall | 68.0% |
| Scaffold command to live traffic | 195 seconds |
| Saturation point | 25 to 30 concurrent users |

Classification accuracy is enforced in CI as a regression gate, so a change that makes the model worse fails the build. The saturation point is limited by memory on a single small node.
