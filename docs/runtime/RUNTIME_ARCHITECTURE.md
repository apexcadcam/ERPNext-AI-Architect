# RUNTIME ARCHITECTURE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [PROJECT_CHARTER.md](../../PROJECT_CHARTER.md) and [ENGINEERING_META_MODEL.md](../../ENGINEERING_META_MODEL.md). Sits *beneath* every previously-frozen architecture document — [Engineering Rules](../../rules/), the [Meta-Model](../../ENGINEERING_META_MODEL.md), [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md), [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md), the [Knowledge Source Catalog](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md), the [Knowledge Acquisition Architecture](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md), and the [Crawler Framework](../crawler/CRAWLER_ARCHITECTURE.md) — none of which are redesigned here. This document set gives them an execution substrate; it does not change what any of them say.
**Scope:** The Core Runtime Platform — the "operating system" every module (Crawler, Parser, Extractor, Validator, Graph, Embedding, Retrieval, Rule Engine, Version Intelligence, Agents, and whatever comes after) plugs into. No implementation, no Python, no class skeletons.

---

## 1. The One Rule Everything Else Follows

**The Runtime knows modules. It does not know ERPNext, Frappe, documentation, rules, or knowledge.** Every domain concept this project has built so far — a `Knowledge Document`, a `Knowledge Conflict`, an `Engineering Rule`, a crawl connector — exists entirely inside a module's own logic, never inside the Runtime's. The Runtime's job is exhausted by four capabilities: load modules, wire their dependencies, route their events, and execute the pipelines they're configured into. If a design decision in any of the eleven documents beneath this one requires the Runtime to understand *what* a `Knowledge Conflict` is, that decision belongs in a module, not here — this is the same discipline already established for `MCP`/`Tool` in [ENGINEERING_META_MODEL.md entries 20–21](../../ENGINEERING_META_MODEL.md#20-mcp-mcp) ("MCP only executes Tools; it holds no architectural judgment of its own"), now applied one layer further down, to the platform those execution boundaries themselves run on.

---

## 2. Two Layers, Not One

| Layer | Knows about | Examples |
|---|---|---|
| **Runtime (this document set)** | Modules, plugins, pipeline *stages* (as opaque named steps), events (as opaque named messages), configuration, storage *adapters*, dependency wiring | Nothing ERPNext-specific appears in any of these twelve documents |
| **Modules (everything built so far, and everything future)** | Their own domain — the Crawler module knows what a `Knowledge Document` is; the Validator module knows [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md)'s eight gates; the Rule Engine module knows what `Engineering Rule` compliance means | [`docs/crawler/`](../crawler/), [`docs/knowledge-pipeline/`](../knowledge-pipeline/), [`docs/ai-retrieval/`](../ai-retrieval/) — every one of these remains authoritative for its own domain, unchanged |

A module carrying deterministic, already-specified domain judgment (the Validator applying [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md)'s gates, the Conflict Resolution logic applying [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](../knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md)'s precedence hierarchy) is not a violation of "the Runtime holds no judgment" — that invariant binds the **Runtime**, not its modules. A module is free to be as domain-aware as its own frozen specification already says it should be; the Runtime's only requirement of it is that it honor the [`MODULE_SYSTEM.md`](MODULE_SYSTEM.md) contract at its boundary.

---

## 3. Why No New ADR

Per the task's own instruction: existing architecture is frozen, and inconsistencies are documented as integration points, not redesigned. Nothing in this document set adds a new Knowledge Artifact type, renames an existing one, or forces a contested choice between rejected alternatives — the three conditions that triggered [ADR-0001](../../adr/ADR-0001-ai-retrieval-metadata-layer.md) and [ADR-0002](../../adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md). "Module," "Plugin," "Pipeline Definition," and "Event" are software-architecture concepts describing *how code runs*, not knowledge-provenance concepts describing *what is known and how much to trust it* — they have no representation in, and make no claim on, the [Knowledge Artifact Catalog](../../ENGINEERING_META_MODEL.md#knowledge-artifact-catalog). The one place this document set touches [`ENGINEERING_META_MODEL.md`](../../ENGINEERING_META_MODEL.md) at all is the same additive folder-mapping courtesy every prior round has extended — reserving where the Runtime's own (not-yet-written) code would live, nothing more.

---

## 4. Integration Points With Frozen Architecture

Documented explicitly, per the task's instruction, rather than silently resolved:

### 4.1 The Pipeline Engine's example vs. `CRAWLER_PIPELINE.md`'s actual stages

The task's illustrative pipeline (Discover → Download → Parse → Normalize → Extract → Validate → Persist → Graph → Embed → Index) does not stage-for-stage match [`CRAWLER_PIPELINE.md`](../crawler/CRAWLER_PIPELINE.md)'s frozen nine stages (Discover → Queue → Download → Validate → Normalize → Parse → Extract Metadata → Persist → Emit Pipeline Event), nor [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md)'s eight gates, nor [`KNOWLEDGE_PIPELINE.md`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md)'s four. **Resolution:** the task's example is illustrative of the *shape* a Pipeline Definition takes on a generic engine, not a mandate to reconcile stage names or ordering across documents. [`PIPELINE_ENGINE.md § 4`](PIPELINE_ENGINE.md#4-existing-pipelines-as-pipeline-definitions) registers `CRAWLER_PIPELINE.md`'s actual nine stages, unmodified, as one concrete Pipeline Definition — the Runtime's engine is generic *because* it doesn't require this reconciliation to ever happen; it executes whatever stage sequence a module declares.

### 4.2 `CRAWLER_PIPELINE.md § 9`'s "Emit Pipeline Event" and the Event Bus

Previously specified only as "publishes one event... to whatever consumes Validation's queue," with no concrete transport. **Resolution:** [`EVENT_BUS.md`](EVENT_BUS.md) is that transport — `Emit Pipeline Event` becomes, concretely, "publish to the Runtime's Event Bus." No change to what `CRAWLER_PIPELINE.md § 9` says the event contains.

### 4.3 `STORAGE_LAYOUT.md`'s deferred storage-product choice

[`STORAGE_LAYOUT.md § 2`](../crawler/STORAGE_LAYOUT.md#2-path-structure) defined logical paths (`raw/`, `documents/`, `cache/`) while explicitly deferring which physical backend serves them. **Resolution:** [`STORAGE_ABSTRACTION.md`](STORAGE_ABSTRACTION.md) is that deferred decision's interface layer — `STORAGE_LAYOUT.md`'s logical zones become namespaces resolved through a Storage Adapter, chosen by configuration, never by a module's own code.

### 4.4 `SOURCE_CONNECTOR_SPEC.md`'s ten declarations and hierarchical configuration

Already a well-formed configuration schema at the connector level. **Resolution:** [`CONFIGURATION_SYSTEM.md § 2`](CONFIGURATION_SYSTEM.md#2-the-six-layers) names "connector" as one of its six layers specifically because [`SOURCE_CONNECTOR_SPEC.md`](../crawler/SOURCE_CONNECTOR_SPEC.md) already populates it — no new connector-configuration concept invented.

### 4.5 Crawler's `OBSERVABILITY.md` and Runtime-wide observability

**Resolution:** [`LOGGING_AND_OBSERVABILITY.md`](LOGGING_AND_OBSERVABILITY.md) generalizes the metrics/logging/tracing/health-check shape [`docs/crawler/OBSERVABILITY.md`](../crawler/OBSERVABILITY.md) already established for the Crawler specifically into a Runtime-wide capability every module gets for free — the Crawler's document remains the authoritative *content* of what it logs; the Runtime only supplies the *mechanism*.

### 4.6 `Rule Engine` module vs. `Engineering Rule` artifact type

Distinct layers, same relationship already established for Source Connector vs. `Knowledge Source` and MCP/Tool vs. the Knowledge Artifact Catalog: the **Rule Engine module** is software that evaluates a proposal against `rules/*.md`; it never redefines what an `Engineering Rule` is, and it carries no authority `docs/ENGINEERING_RULE_SPECIFICATION.md` doesn't already grant it.

### 4.7 `Agents` module vs. `Agent (AG)` artifact type

Not a new concept — the Agents module is the Runtime's execution host for instantiating and running `Agent` artifacts, composed from `Skill`s, exactly as [`ENGINEERING_META_MODEL.md`](../../ENGINEERING_META_MODEL.md#15-agent-ag) already defines. The Runtime gives Agents a place to run; it does not change what an Agent is built from.

### 4.8 `Version Intelligence` — a new module name for already-specified logic

Consolidates version-scoping ([`KNOWLEDGE_PIPELINE.md § 4`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#4-normalization-stage-3-detail)), staleness propagation and breaking-change handling ([`KNOWLEDGE_REFRESH_POLICY.md`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md)), and the Crawler's own component versioning ([`VERSIONING_POLICY.md`](../crawler/VERSIONING_POLICY.md)) under one module name. The module is new; every rule it executes is not.

---

## 5. Core Principles, and Where Each Is Addressed

| Principle | Primarily addressed in |
|---|---|
| Plugin-first | [`MODULE_SYSTEM.md`](MODULE_SYSTEM.md), [`PLUGIN_REGISTRY.md`](PLUGIN_REGISTRY.md) |
| Event-driven | [`EVENT_BUS.md`](EVENT_BUS.md) |
| Dependency-injected | [`DEPENDENCY_INJECTION.md`](DEPENDENCY_INJECTION.md) |
| Modular | [`MODULE_SYSTEM.md`](MODULE_SYSTEM.md) |
| Testable | [`DEPENDENCY_INJECTION.md § 4`](DEPENDENCY_INJECTION.md#4-test-doubles) (injectable test doubles); reuses [`docs/crawler/TESTING_STRATEGY.md`](../crawler/TESTING_STRATEGY.md)'s fixture discipline at the Runtime level |
| Observable | [`LOGGING_AND_OBSERVABILITY.md`](LOGGING_AND_OBSERVABILITY.md) |
| Deterministic | [`PIPELINE_ENGINE.md`](PIPELINE_ENGINE.md)'s fixed stage-execution contract; [`EVENT_BUS.md`](EVENT_BUS.md)'s delivery guarantees |
| Source-agnostic | [§1](#1-the-one-rule-everything-else-follows) — structurally guaranteed, not merely aspired to |
| AI-independent | No module, including Agents, is a Runtime dependency — see [§6](#6-ai-independence) |

## 6. AI Independence

The Runtime has no concept of a model, a prompt, or an inference call — it schedules and wires modules, one of which (Agents) happens to invoke AI systems as part of its *own* internal logic, invisible to the Runtime itself. This is the same principle [`ENGINEERING_META_MODEL.md § Design Principles`](../../ENGINEERING_META_MODEL.md#design-principles) already states for the knowledge layer ("No artifact's validity depends on a specific AI vendor or model"), extended downward: the platform beneath the knowledge layer is exactly as vendor-independent as the knowledge layer itself claims to be.

---

## 7. Non-Functional Requirements at Scale

"Hundreds of plugins, millions of artifacts, parallel execution, future distributed execution, future remote workers, future cloud deployment — without redesign" is a claim about **where extension points already are**, not a claim this document set builds distributed infrastructure today. Every document below identifies its own extension point for this: [`PLUGIN_REGISTRY.md`](PLUGIN_REGISTRY.md) never assumes plugin count, [`PIPELINE_ENGINE.md`](PIPELINE_ENGINE.md) never assumes single-process execution, [`STORAGE_ABSTRACTION.md`](STORAGE_ABSTRACTION.md) never assumes a local filesystem, [`EVENT_BUS.md`](EVENT_BUS.md) never assumes in-process delivery. None of these are implemented as distributed today — the requirement is that nothing in the *architecture* would need to change when they eventually are.

---

## 8. Document Map

| Document | Answers |
|---|---|
| [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md) | This document. |
| [MODULE_SYSTEM.md](MODULE_SYSTEM.md) | What must every module declare and implement to participate? |
| [PLUGIN_REGISTRY.md](PLUGIN_REGISTRY.md) | How are modules discovered, enabled/disabled, and dependency-checked? |
| [DEPENDENCY_INJECTION.md](DEPENDENCY_INJECTION.md) | How do modules get each other, without instantiating each other directly? |
| [PIPELINE_ENGINE.md](PIPELINE_ENGINE.md) | How are configurable, retryable, rollback-capable pipelines executed? |
| [EVENT_BUS.md](EVENT_BUS.md) | How do modules communicate without the Runtime knowing what they're saying? |
| [CONFIGURATION_SYSTEM.md](CONFIGURATION_SYSTEM.md) | How does hierarchical, versioned, validated configuration work? |
| [STORAGE_ABSTRACTION.md](STORAGE_ABSTRACTION.md) | How does the Runtime stay ignorant of filesystem vs. S3 vs. database? |
| [LOGGING_AND_OBSERVABILITY.md](LOGGING_AND_OBSERVABILITY.md) | How is the whole running system seen, correlated, and traced? |
| [CLI_ARCHITECTURE.md](CLI_ARCHITECTURE.md) | How does `architect` map onto Runtime operations? |
| [LIFECYCLE.md](LIFECYCLE.md) | What states do a module, a pipeline run, and the Runtime process itself move through? |
| [RUNTIME_BOOT_SEQUENCE.md](RUNTIME_BOOT_SEQUENCE.md) | What actually happens between process start and "ready"? |

---

## 9. What Happens Next (Explicitly Out of Scope Here)

Architecture only — no plugin loader, no DI container, no event bus, no CLI has been built. Implementation is separately-scoped future work, gated by the same Architecture Review discipline already applied twice before ([`KNOWLEDGE_ACQUISITION_ARCHITECTURE.md § 6`](../knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md#6-what-happens-next-explicitly-out-of-scope-here), [`CRAWLER_ARCHITECTURE.md § 5`](../crawler/CRAWLER_ARCHITECTURE.md#5-what-happens-next-explicitly-out-of-scope-here)).
