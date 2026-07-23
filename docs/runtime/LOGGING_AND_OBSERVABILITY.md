# LOGGING AND OBSERVABILITY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md § 4.5](RUNTIME_ARCHITECTURE.md#45-crawlers-observabilitymd-and-runtime-wide-observability). Generalizes [`docs/crawler/OBSERVABILITY.md`](../crawler/OBSERVABILITY.md)'s shape (logging, metrics, tracing, health checks, progress reporting) from the Crawler module specifically to every module in the Runtime.
**Scope:** The shared observability substrate. Content ownership (what a module's logs/metrics actually mean) stays with that module's own frozen specification.

---

## 1. Structured Logging

Every log entry, from every module, carries the same minimum correlation fields — `correlation_id`, `pipeline_run_id`, `module_id`, `stage` (where applicable) — a direct extension of [`docs/crawler/OBSERVABILITY.md § 1`](../crawler/OBSERVABILITY.md#1-logging)'s existing requirement, now enforced at the Runtime's shared logging facility rather than as a convention each module would otherwise have to reimplement independently. No literal credential value, and no full response/document body at normal log levels, is ever logged — the same two rules already stated there, unchanged, now structurally guaranteed because every module logs *through* this shared facility rather than to its own output stream.

## 2. Correlation

Three IDs, not one, because they answer different questions:

| ID | Answers | Assigned at |
|---|---|---|
| `correlation_id` | "which single unit of work is this?" (one Crawl Item, one artifact's extraction, one validation pass) | The earliest point that unit of work exists — [`CRAWLER_PIPELINE.md § 1`](../crawler/CRAWLER_PIPELINE.md#1-discover) for a crawled document |
| `pipeline_run_id` | "which execution of a Pipeline Definition produced this?" | [`PIPELINE_ENGINE.md`](PIPELINE_ENGINE.md) run start |
| `artifact_id` | "which specific, permanently-identified artifact is this about?" | Once an artifact is actually created (a `Knowledge Document`, a `Knowledge API`, an `Engineering Rule` candidate) |

A single `correlation_id` may span multiple `pipeline_run_id`s (a document acquired in one `crawler.acquisition` run, later validated in a separate `knowledge.validation` run) and accumulate multiple `artifact_id`s (one source document producing several extracted artifacts) — all three IDs are carried in every event on the [Event Bus](EVENT_BUS.md#1-the-bus-knows-topics-not-meaning) and every Pipeline Engine stage invocation ([`PIPELINE_ENGINE.md § 2`](PIPELINE_ENGINE.md#2-stage-execution-contract)'s `pipeline_context`), which is what makes end-to-end tracing possible without any single module needing to understand the whole journey itself.

## 3. Metrics

Every module reports metrics through the same shared interface; content is module-defined, per [`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest)'s manifest. [`docs/crawler/OBSERVABILITY.md § 2`](../crawler/OBSERVABILITY.md#2-metrics)'s existing metric table (queue depth, download success rate, rate-limit utilization, cache hit rate, parse success rate, end-to-end latency) remains exactly as specified for the Crawler module — this document adds nothing to *what* it measures, only *how* every module's metrics reach one shared aggregation point instead of each module needing its own reporting mechanism.

## 4. Health Checks

The Runtime-wide generalization of [`MODULE_SYSTEM.md § 3`](MODULE_SYSTEM.md#3-the-module-lifecycle-interface)'s `health_check()` hook — every module reports `{ healthy: bool, detail }` through the identical shape, and for the Crawler module specifically this wraps, unmodified, [`docs/crawler/OBSERVABILITY.md § 4`](../crawler/OBSERVABILITY.md#4-health-checks)'s existing per-connector health record. `architect doctor` ([`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md)) is this capability surfaced as a single command, querying every registered module's `health_check()` in one pass.

## 5. Tracing

One distributed trace per `correlation_id`, spanning every Pipeline Engine stage and every Event Bus hop that `correlation_id` touches — the Runtime-wide realization of [`docs/crawler/OBSERVABILITY.md § 3`](../crawler/OBSERVABILITY.md#3-tracing)'s claim that a trace "can, in principle, be followed past the Crawler Framework's own boundary" — this document is where that principle actually becomes true, because the trace mechanism is now the same one on both sides of that boundary rather than two separate systems that happen to use compatible ID formats.

## 6. Progress Reporting

Per pipeline run: aggregated from every stage's [`PIPELINE_ENGINE.md § 7`](PIPELINE_ENGINE.md#7-metrics-and-tracing) metrics into one run-level view — `{ pipeline_run_id, stages_completed, stages_remaining, items_processed, items_failed (by category), estimated_completion }` — the same shape [`docs/crawler/OBSERVABILITY.md § 5`](../crawler/OBSERVABILITY.md#5-progress-reporting) already defined for one Pipeline Definition (`crawler.acquisition`), now available uniformly for any Pipeline Definition registered per [`PIPELINE_ENGINE.md § 4`](PIPELINE_ENGINE.md#4-existing-pipelines-as-pipeline-definitions).

## 7. What This Layer Never Does

Restated from [`docs/crawler/OBSERVABILITY.md § 6`](../crawler/OBSERVABILITY.md#6-what-observability-never-does), one layer up: observability reports on mechanical health and progress — it never reports on, or influences, a `Knowledge Source`'s Trust Score, an artifact's confidence, or a Rule's status. A perfectly healthy Runtime processing a low-trust source is still processing a low-trust source; this layer and the epistemic-judgment layers above it answer different questions and are never conflated into one signal.
