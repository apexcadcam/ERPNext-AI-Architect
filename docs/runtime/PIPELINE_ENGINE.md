# PIPELINE ENGINE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md § 4.1](RUNTIME_ARCHITECTURE.md#41-the-pipeline-engines-example-vs-crawler_pipelinemds-actual-stages), whose integration-point reasoning this document implements in full.
**Scope:** A generic stage-sequencing and execution engine — configurable pipelines, dynamic stages, retries, rollback, metrics, tracing. It does not define what any stage *means*; every existing pipeline (Crawler's nine stages, Knowledge Pipeline's four, Knowledge Validation's eight gates) registers as a Pipeline Definition running on this engine, unmodified.

---

## 1. A Pipeline Definition Is Data, Not Code

A Pipeline Definition is a declared, ordered (or partially-ordered, per [§3](#3-dynamic-stages)) list of named stages, each stage bound to a module capability (per [`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest)'s `pipeline_stage_bindings`) — the Engine reads this declaration and executes it; it never has stage logic of its own compiled in. This is what "configurable pipelines" means concretely: a new pipeline (or a modified stage order for an existing one) is a configuration change, per [`CONFIGURATION_SYSTEM.md`](CONFIGURATION_SYSTEM.md)'s pipeline layer, never a Runtime code change.

## 2. Stage Execution Contract

Every stage, regardless of which pipeline it belongs to, is invoked with exactly the same shape: `(input, pipeline_context) → (output, stage_result)`. `pipeline_context` carries the correlation ID, pipeline-run ID, and accumulated trace (per [`LOGGING_AND_OBSERVABILITY.md § 2`](LOGGING_AND_OBSERVABILITY.md#2-correlation)); `stage_result` reports success, failure-with-category, or retry-requested. The Engine never inspects `input`/`output` beyond passing them through — this is the direct generalization of [`CRAWLER_PIPELINE.md § 0`](../crawler/CRAWLER_PIPELINE.md#0-the-crawl-item--one-contract-nine-consumers)'s Crawl Item contract: that document specified one concrete item shape for one concrete pipeline; this document specifies the *shape of the contract itself*, of which the Crawl Item is one instance.

## 3. Dynamic Stages

A Pipeline Definition's stage list is resolved at run-start from configuration, not compiled into the Engine — a stage can be added, removed, or reordered for a given pipeline (and, for advanced cases, conditionally included based on `pipeline_context`, e.g., skip Embedding for a run explicitly scoped to validation-only) without touching the Engine itself. "Dynamic" means *configured per run*, not *decided by the Engine's own logic* — the Engine remains deterministic ([`RUNTIME_ARCHITECTURE.md § 5`](RUNTIME_ARCHITECTURE.md#5-core-principles-and-where-each-is-addressed)) because a given configuration always produces the same stage sequence.

## 4. Existing Pipelines as Pipeline Definitions

| Pipeline Definition | Stages (unmodified from their frozen source) | Source of truth |
|---|---|---|
| `crawler.acquisition` | Discover, Queue, Download, Validate (transport), Normalize, Parse, Extract Metadata, Persist, Emit Event | [`CRAWLER_PIPELINE.md`](../crawler/CRAWLER_PIPELINE.md), verbatim |
| `knowledge.formation` | Acquisition (delegates to `crawler.acquisition`), Cleaning, Normalization, Deduplication | [`KNOWLEDGE_PIPELINE.md`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md), verbatim |
| `knowledge.graph_build` | Extraction, Pattern Extraction, Conflict Resolution, Graph Node/Edge Materialization | [`KNOWLEDGE_EXTRACTION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md), [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](../knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md), [`KNOWLEDGE_GRAPH_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md) |
| `knowledge.validation` | Schema Validation, Duplicate Detection, Version Conflict Detection, Source Verification, Trust Verification, Engineering Review, Human Approval Gate, Confidence Scoring | [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md), verbatim — note this pipeline's stages are strictly ordered and non-parallel, per that document's [§0](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#0-why-order-is-fixed-not-parallel) |
| `knowledge.retrieval_index` | Embedding, Indexing | [`EMBEDDING_STRATEGY.md`](../knowledge-pipeline/EMBEDDING_STRATEGY.md), [`RETRIEVAL_STRATEGY.md`](../knowledge-pipeline/RETRIEVAL_STRATEGY.md) |

The task's illustrative example (Discover → Download → Parse → Normalize → Extract → Validate → Persist → Graph → Embed → Index) is not itself registered as a Pipeline Definition — it is a *composite* view spanning all five definitions above end to end, exactly the shape [`docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md § 2`](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md#2-the-pipeline-end-to-end)'s own diagram already draws across multiple frozen documents. The Engine can compose definitions end to end (chaining `crawler.acquisition`'s output into `knowledge.formation`'s input, and so on) without any of the five needing to be a single monolithic definition — composition is itself just another configuration.

## 5. Retries

**Stage-level, generic, and distinct from module-internal retry.** A Pipeline Definition may declare a stage retryable with a max-attempts and backoff policy — this is the orchestration-level safety net. It does not replace [`docs/crawler/RETRY_POLICY.md`](../crawler/RETRY_POLICY.md)'s network-failure-specific retry logic, which continues to run *inside* a single attempt of the Crawler module's Download stage; the Engine's stage-level retry only re-invokes the whole stage if the module reports `stage_result: retry-requested` after its own internal retry policy has been exhausted, per [`ERROR_HANDLING.md § 1`](../crawler/ERROR_HANDLING.md#1-recoverable)'s escalation to a circuit-breaker-level signal.

## 6. Rollback

**Never physical deletion — always a compensating state transition**, consistent with every prior document's "never delete, only supersede/mark-invalid" discipline. A stage that writes artifacts (Persist, Graph Node/Edge Materialization) declares a compensating action for rollback: marking the produced artifact(s) `rolled_back` rather than removing them, preserving the audit trail [`STORAGE_LAYOUT.md § 4`](../crawler/STORAGE_LAYOUT.md#4-retention) and [`KNOWLEDGE_GRAPH_SPEC.md § 4`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules) already require. A pipeline run that fails at stage N triggers rollback of stages 1..N-1's compensating actions, in reverse order, before the run is marked `failed` — see [`LIFECYCLE.md § 4`](LIFECYCLE.md#4-pipeline-run-states) for the full run-state machine this feeds into.

## 7. Metrics and Tracing

Every stage execution emits duration, outcome, and retry-count metrics, and participates in the distributed trace keyed by `pipeline_context`'s correlation ID — the Engine-level generalization of [`docs/crawler/OBSERVABILITY.md § 3`](../crawler/OBSERVABILITY.md#3-tracing)'s per-Crawl-Item trace, now spanning every Pipeline Definition, not just the Crawler's. Full design in [`LOGGING_AND_OBSERVABILITY.md`](LOGGING_AND_OBSERVABILITY.md).

## 8. Parallel and Future Distributed Execution

Two independent Crawl Items (or, generically, two independent pipeline-context instances with no `depends_on` relationship between them) may execute concurrently through the same Pipeline Definition — the stage contract in [§2](#2-stage-execution-contract) has no shared mutable state between concurrent runs by construction, which is what makes both today's in-process parallelism and a future distributed worker pool ([`RUNTIME_ARCHITECTURE.md § 7`](RUNTIME_ARCHITECTURE.md#7-non-functional-requirements-at-scale)) the same architecture, differing only in *where* a stage's invocation physically executes, never in *how* the Engine sequences and tracks it.
