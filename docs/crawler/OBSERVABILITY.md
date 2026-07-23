# OBSERVABILITY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). What makes the "Observable" non-functional requirement ([`CRAWLER_ARCHITECTURE.md § 3`](CRAWLER_ARCHITECTURE.md#3-non-functional-requirements-and-where-each-is-addressed)) concrete.
**Scope:** Logging, metrics, tracing, health checks, progress reporting. No code, no product choice (no mandated logging/metrics/tracing vendor).

---

## 1. Logging

**Structured, not free-text** — every log entry carries, at minimum, `crawl_run_id`, `connector_id`, `stage` (one of [`CRAWLER_PIPELINE.md`](CRAWLER_PIPELINE.md)'s nine), and `dedupe_key`/`knowledge_document_id` once assigned — so a single crawl item's full journey through all nine stages is reconstructable by filtering on one correlation key, per [§3](#3-tracing).
**What is never logged:** raw credential values (per [`SOURCE_CONNECTOR_SPEC.md § 1.2`](SOURCE_CONNECTOR_SPEC.md#12-authentication)'s "never a literal secret" rule, extended here to logs specifically, a common leak vector this rule exists to close), and full response bodies at normal log levels (available on-demand via [`STORAGE_LAYOUT.md`](STORAGE_LAYOUT.md)'s `raw/` zone instead of duplicated into logs).

## 2. Metrics

| Metric | Purpose |
|---|---|
| Queue depth, per connector | Detects a connector falling behind its discovery rate |
| Download success/failure rate, per connector, per [`ERROR_HANDLING.md`](ERROR_HANDLING.md) category | The primary health signal — a rising Recoverable-failure rate against an otherwise-stable connector is the earliest warning of a source-side problem |
| Rate-limit budget utilization, per [`RATE_LIMITING.md § 1`](RATE_LIMITING.md#1-three-budgets-checked-in-order)'s three budgets | Distinguishes "slow because the source is slow" from "slow because we're self-throttling correctly" |
| Cache hit rate ([`CACHE_STRATEGY.md`](CACHE_STRATEGY.md)) | A sudden drop signals either genuine mass content change (expected occasionally) or a cache-invalidation bug (not expected) — the two are distinguished by cross-referencing against [`KNOWLEDGE_REFRESH_POLICY.md`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md)'s breaking-change signals |
| Parse success rate, per content-type | A drop isolated to one content-type points at [`ERROR_HANDLING.md § Parsing`](ERROR_HANDLING.md#5-parsing) needing attention for that parser specifically |
| End-to-end latency, Discover → Emit Event | The throughput metric that actually matters for "high-performance," as opposed to any single stage's latency in isolation |

## 3. Tracing

Every Crawl Item is tagged, at Discover, with a trace ID that persists through every subsequent stage and is carried into the `Emit Pipeline Event` payload ([`CRAWLER_PIPELINE.md § 9`](CRAWLER_PIPELINE.md#9-emit-pipeline-event)) — meaning a trace can, in principle, be followed **past** the Crawler Framework's own boundary into [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md)'s gates and beyond, giving one continuous, auditable trail from "a URL was discovered" to "this fact is now retrievable by an agent" — the single strongest concrete expression of this project's standing Traceability principle, spanning both architecture layers without either needing to know the other's internals.

## 4. Health Checks

Per connector: `{ reachable: bool, credentials_valid: bool, last_successful_crawl: timestamp, consecutive_failures: int, circuit_state: closed | open }` — directly surfaces [`RETRY_POLICY.md § 3`](RETRY_POLICY.md#3-circuit-breaker)'s circuit-breaker state and feeds [`KNOWLEDGE_REFRESH_POLICY.md § 5`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#5-deprecation-and-retirement)'s unreachable-source flag directly — this is the one piece of state both documents need, defined once, here, and referenced by both rather than tracked twice.

## 5. Progress Reporting

Per crawl run: `{ discovered_count, queued_count, downloaded_count, persisted_count, failed_count (by category), estimated_completion }`, compared against [`SOURCE_CONNECTOR_SPEC.md § 1.3`](SOURCE_CONNECTOR_SPEC.md#13-discovery-strategy)'s declared `expected_candidate_volume` — a run whose `discovered_count` wildly exceeds or falls short of that estimate is itself a signal (a connector's discovery strategy may have broken, or the source genuinely grew) surfaced *during* the run, not only discovered after the fact by comparing final counts.

## 6. What Observability Never Does

Per [`CRAWLER_ARCHITECTURE.md § 2.1`](CRAWLER_ARCHITECTURE.md#21-where-this-frameworks-output-boundary-is): observability reports on the *mechanical* health of crawling — it never reports on, or influences, a source's Trust Score or an artifact's confidence. A connector with a perfect health-check record crawling a low-trust source is still a low-trust source; observability and epistemic trust are answering different questions and must never be conflated into one dashboard number.
