# RATE LIMITING

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Gates admission from [`CRAWLER_PIPELINE.md § 2`](CRAWLER_PIPELINE.md#2-queue) into [§ 3](CRAWLER_PIPELINE.md#3-download).
**Scope:** How politeness and platform-quota compliance are enforced, per host, per connector, and globally, under contention. No code.

---

## 1. Three Budgets, Checked in Order

1. **Host-level budget** — the politeness ceiling for a specific host (e.g., 1 req/sec to `docs.frappe.io`), independent of which connector is asking. Two connectors that happen to target the same host (unlikely today, plausible once hundreds of connectors exist) share this budget rather than each independently exceeding it.
2. **Connector-level budget** — the platform-specific quota declared in [`SOURCE_CONNECTOR_SPEC.md § 1.7`](SOURCE_CONNECTOR_SPEC.md#17-rate-limits) (GitHub's 5,000/hr authenticated, YouTube's daily quota units, Stack Exchange's daily cap).
3. **Global budget** — a system-wide concurrency/throughput ceiling, protecting the framework's own infrastructure (outbound bandwidth, worker pool size) independent of any single source's willingness to accept more traffic.

A request must clear all three before Download runs. Whichever is tightest at that moment determines the actual wait.

## 2. Token Bucket, Per Budget

Each of the three budgets above is modeled as an independent token bucket: tokens refill at the budget's declared rate, a request consumes one token, and a request arriving to an empty bucket queues rather than firing early. This is a standard, well-understood rate-limiting shape, specified here architecturally (bucket size, refill rate, queuing behavior) without prescribing an implementation.

## 3. Respecting Platform-Provided Signals

For any connector declaring `respects_platform_headers: true` ([`SOURCE_CONNECTOR_SPEC.md § 1.7`](SOURCE_CONNECTOR_SPEC.md#17-rate-limits)): the platform's own returned rate-limit headers (GitHub's `X-RateLimit-Remaining`/`X-RateLimit-Reset`, Discourse's `Retry-After`, Stack Exchange's `quota_remaining`) **always override** the connector's locally-tracked bucket state the moment they're observed — the framework's own token count is a prediction, the platform's header is ground truth, and ground truth wins on every request, per [`KNOWLEDGE_PIPELINE.md § 1`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#1-acquisition-method-by-source-type)'s existing per-source-type policy table, now given the actual reconciliation mechanism it didn't previously specify.

## 4. Priority-Based Allocation Under Contention

When the global budget is the binding constraint (more connectors ready to fetch than throughput allows), admission order is **not** first-come-first-served — it follows the [Knowledge Source Catalog](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md)'s own Priority field (`P0` sources admitted ahead of `P1`, ahead of `P2`, and so on), the same ordering already established for [crawl sequencing](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md#11-recommended-crawl-order) — rate limiting under contention is that same priority applied continuously during live operation, not just at initial rollout.

## 5. Backoff Coordination Across Concurrent Workers

When a host or connector-level budget is exhausted, **every** worker targeting that same budget backs off together, reading from the same shared bucket state — never each independently guessing a wait time and collectively over- or under-shooting the actual limit. This is what makes [§1](#1-three-budgets-checked-in-order)'s "shared per-host budget across connectors" claim actually true under real concurrency, not just true in the single-worker case.

## 6. Interaction with Retry

A `429` response is not, by itself, a rate-limiting-layer event — it is a [`RETRY_POLICY.md`](RETRY_POLICY.md) event that *also* feeds back into this layer: receiving a `429` immediately zeroes the relevant bucket's remaining tokens (regardless of what the framework's own prediction said) and applies any `Retry-After` value as the bucket's next refill time, per [§3](#3-respecting-platform-provided-signals)'s ground-truth-wins rule. Rate limiting and retry are two views of the same underlying signal, kept consistent rather than reasoned about independently.
