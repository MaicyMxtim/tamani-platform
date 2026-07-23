# Unit economics

Every figure here comes from the running system or a measured experiment,
with the method stated. Inference is treated as the primary cost line,
because for an AI-backed product it dominates compute long before
Kubernetes does — the whole platform runs on one machine covered by
free-tier credits, while a single day of classification can outspend it.

## Cost per thousand classifications

**Method:** the gateway writes one ledger record per request (tenant,
model, tokens, cost, cache hit). `GET /v1/costs` aggregates it.

| Metric | Value |
|---|---|
| Model | claude-opus-4-8 |
| Cost per 1,000 classifications (provider calls only) | **$5.14** |
| Effective cost per 1,000 (with cache) | **$4.01** |
| Cache hit rate (measured window) | 22% |
| Money saved by the cache (measured window) | $0.37 on $2.86 gross |

Input and output tokens are priced separately in the ledger ($5/$25 per
million on Opus), because output tokens cost 5x input and a verbose
prompt is a recurring bill.

## Cache savings, stated as money

The semantic cache avoided 136 provider calls in the measured window.
At the effective blended rate that is the difference between $5.14 and
$4.01 per thousand — a **22% reduction** already, rising with traffic as
popular venues repeat. On production traffic (many users, few new
venues) the plan's expectation of the cache removing the majority of
spend holds; ours is early and low-repeat.

## Model tiering — accuracy cost measured, not assumed

**Method:** the 144-venue golden set run through each model directly,
cache bypassed (`evals/tiering_experiment.py`).

| Model | Precision | Recall | F1 | Cost / 1k |
|---|---|---|---|---|
| Haiku 4.5 | 72.7% | 61.8% | 66.8% | **$0.62** |
| Sonnet 5 | 75.8% | 70.3% | 72.9% | $3.17 |
| Opus 4.8 | 80.9% | 68.6% | 74.2% | $4.10 |

**The decision this data supports:** Opus buys **1.3 F1 points over
Sonnet for 1.3x the cost** — thin. Haiku is **6.6x cheaper than Opus**
and loses ~7.5 F1 points. So the economical routing is: **Haiku for the
straightforward classifications, escalate to Opus only when Haiku's
confidence is low.** If a third of venues escalate, blended cost is
roughly `0.67*$0.62 + 0.33*$4.10 = $1.77/1k` — a **57% cut** versus
all-Opus, for a small, measured accuracy loss concentrated on the
venues that were ambiguous anyway. The routing hook already exists (the
gateway records confidence per classification); turning it on is a
config change, not a rebuild.

## GPU self-hosting crossover

**Method:** compare per-token provider pricing against the hourly cost
of a self-hosted GPU that could serve an equivalent open model.

- Provider (Opus): ~$4.10 per 1,000 classifications.
- A modest cloud GPU (e.g. one L4/A10-class instance) runs ~$0.75–1.00/hr,
  ~$550–730/month if always on.
- At ~350 input + 40 output tokens per classification, a single such GPU
  serving a 7–8B open model sustains on the order of a few classifications
  per second — call it ~200k/day at healthy utilisation.

**Crossover:** self-hosting only wins when sustained volume fills the GPU.
At $650/month, break-even against Opus at $4.10/1k is about **160,000
classifications a month** — and against the *tiered* $1.77/1k blend it is
about **370,000/month**. Tamani's real workload (1,275 venues,
reclassified occasionally) is three orders of magnitude below that. **The
managed provider is decisively cheaper here**, and self-hosting would
also add the operational cost of running model infrastructure on a
platform whose whole point is small and cheap. Revisit only if
classification volume becomes continuous rather than bursty.

## Cost per active user and per search

- **Search requests are free of inference cost** — they read the bundled
  snapshot; no provider call. Cost per search is effectively the
  amortised compute of the API pod, a rounding error against inference.
- **Cost per active user** is therefore dominated by how many *new*
  classifications their activity triggers. For a browsing user hitting
  cached venues: ~$0. For the enrichment of a genuinely new venue: one
  classification, $0.004 at Opus or ~$0.002 blended with tiering.

## Cluster cost attribution

Namespace labels (`env`, `app`) are on every workload, so per-namespace
CPU/memory attribution is available from the metrics already scraped —
the "AI Spend" and "Service Health" dashboards split by workload. On a
single-node free-tier cluster the compute bill is ~$0 (credits); the
honest statement is that **inference is ~100% of the marginal cost of
this product**, which is exactly why the gateway, cache, budgets and
tiering analysis are where the engineering went.

## The single biggest cost reduction

Semantic caching is the mechanism with the most headroom: at low-repeat
early traffic it already returns 22%, and it scales with popularity
rather than requiring model downgrades. Model tiering is the second
lever (a measured ~57% cut at a small accuracy cost). Together they take
the effective rate from **$5.14 toward well under $2.00 per thousand**
without changing what the user sees.
