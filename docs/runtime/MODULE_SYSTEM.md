# MODULE SYSTEM

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md). The fixed contract every module — Crawler, Parser, Extractor, Validator, Knowledge Graph, Embedding, Retrieval, Rule Engine, Version Intelligence, Agents, and every future module — implements. Governs *what a module is*; [`PLUGIN_REGISTRY.md`](PLUGIN_REGISTRY.md) governs *how it gets discovered and activated*.
**Scope:** The module manifest and lifecycle interface. No code.

---

## 1. A Module Is a Declaration, Not an Assumption

Nothing about the Runtime hardcodes "there is a Crawler module." A module exists because it declares itself against this contract; the Runtime never special-cases any module by name, per [`RUNTIME_ARCHITECTURE.md § 1`](RUNTIME_ARCHITECTURE.md#1-the-one-rule-everything-else-follows). This is the direct generalization of [`CRAWLER_PLUGIN_SYSTEM.md § 2`](../crawler/CRAWLER_PLUGIN_SYSTEM.md#2-registration-not-modification)'s "registration, not modification" principle, lifted from *connectors-within-the-Crawler-module* to *modules-within-the-Runtime* — the same fractal shape at the layer above.

---

## 2. The Module Manifest

Every module declares, once, at registration:

| Field | Description |
|---|---|
| `module_id` | Stable, permanent — same discipline as every other ID in this repository. |
| `display_name`, `maintained_by`, `version` | Identity, per [`VERSIONING_POLICY.md`](../crawler/VERSIONING_POLICY.md)'s semver discipline generalized from connectors/parsers to modules. |
| `capabilities_provided` | What this module can do, expressed as named capabilities other modules or the CLI can request (e.g., `document.persist`, `graph.query`, `rule.evaluate`) — never as a concrete class or function reference, since nothing outside the module ever calls into it directly (see [`DEPENDENCY_INJECTION.md`](DEPENDENCY_INJECTION.md)). |
| `capabilities_required` | What this module needs from others, by capability name, not by module name — a Validator module declares it needs `document.read` and `storage.write`, never "the Crawler module specifically," so a future second document-source module satisfies the same dependency without the Validator's manifest changing. |
| `pipeline_stage_bindings` | Which named pipeline stages (per [`PIPELINE_ENGINE.md`](PIPELINE_ENGINE.md)) this module implements, if any. |
| `events_published`, `events_subscribed` | The event types (by name, per [`EVENT_BUS.md`](EVENT_BUS.md)) this module emits and listens for — declared, never inferred at runtime. |
| `config_schema_ref` | Where this module's own configuration schema lives, consumed by [`CONFIGURATION_SYSTEM.md`](CONFIGURATION_SYSTEM.md)'s module layer. |
| `enabled_by_default` | Whether [`PLUGIN_REGISTRY.md`](PLUGIN_REGISTRY.md) activates this module without explicit opt-in. |

## 3. The Module Lifecycle Interface

Every module implements four lifecycle hooks, invoked by the Runtime at the points defined in [`LIFECYCLE.md`](LIFECYCLE.md) and [`RUNTIME_BOOT_SEQUENCE.md`](RUNTIME_BOOT_SEQUENCE.md):

1. **`validate()`** — checks the module's own configuration and declared dependencies are satisfiable, *before* anything is instantiated; a module that fails validation never reaches `init()`, per [`RUNTIME_BOOT_SEQUENCE.md § 3`](RUNTIME_BOOT_SEQUENCE.md#3-dependency-validation).
2. **`init(container)`** — receives the [Dependency Injection Container](DEPENDENCY_INJECTION.md), resolves its declared `capabilities_required`, and constructs its internal state. A module never reaches outside the container it's handed — reaching for a global, a hardcoded import, or another module's internals directly is a contract violation, not a style preference.
3. **`start()`** — begins whatever ongoing behavior the module provides (subscribing to events, registering pipeline stage handlers, opening connections its declared dependencies provide access to).
4. **`stop()`** — releases everything acquired in `start()`, cleanly, and is guaranteed to be called even on an abnormal Runtime shutdown, per [`LIFECYCLE.md § 3`](LIFECYCLE.md#3-shutdown-ordering).
5. **`health_check()`** — returns the module's current health, consumed by [`LOGGING_AND_OBSERVABILITY.md § 4`](LOGGING_AND_OBSERVABILITY.md#4-health-checks) and, for the Crawler module specifically, wrapping [`docs/crawler/OBSERVABILITY.md § 4`](../crawler/OBSERVABILITY.md#4-health-checks)'s existing per-connector health shape without redefining it.

## 4. Module Isolation

A module's internal state is never directly visible to another module — all cross-module interaction happens through capabilities resolved via the Container ([`DEPENDENCY_INJECTION.md`](DEPENDENCY_INJECTION.md)) or events published to the Bus ([`EVENT_BUS.md`](EVENT_BUS.md)). This is what makes [`PLUGIN_REGISTRY.md`](PLUGIN_REGISTRY.md)'s enable/disable and [`LIFECYCLE.md`](LIFECYCLE.md)'s independent module restart both safe: disabling or restarting one module can never leave another module holding a stale direct reference into it, because no such reference is ever allowed to exist.

## 5. Domain Modules Already Specified

This document does not re-specify what any of these modules *do* — only that they conform to this contract. Their actual behavior remains exactly as already frozen:

| Module | Behavior specified in |
|---|---|
| Crawler | [`docs/crawler/`](../crawler/) — the module hosts its own nested plugin system (Source Connectors, per [`CRAWLER_PLUGIN_SYSTEM.md`](../crawler/CRAWLER_PLUGIN_SYSTEM.md)), unchanged |
| Parser | [`docs/crawler/PARSER_SPEC.md`](../crawler/PARSER_SPEC.md) |
| Extractor | [`docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md) |
| Validator | [`docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md) |
| Knowledge Graph | [`docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md) |
| Embedding | [`docs/knowledge-pipeline/EMBEDDING_STRATEGY.md`](../knowledge-pipeline/EMBEDDING_STRATEGY.md) |
| Retrieval | [`docs/knowledge-pipeline/RETRIEVAL_STRATEGY.md`](../knowledge-pipeline/RETRIEVAL_STRATEGY.md), [`docs/ai-retrieval/RULE_INDEX_SPEC.md`](../ai-retrieval/RULE_INDEX_SPEC.md) |
| Rule Engine | [`docs/ENGINEERING_RULE_SPECIFICATION.md`](../ENGINEERING_RULE_SPECIFICATION.md), [`docs/ai-retrieval/`](../ai-retrieval/) — per [`RUNTIME_ARCHITECTURE.md § 4.6`](RUNTIME_ARCHITECTURE.md#46-rule-engine-module-vs-engineering-rule-artifact-type) |
| Version Intelligence | Consolidated per [`RUNTIME_ARCHITECTURE.md § 4.8`](RUNTIME_ARCHITECTURE.md#48-version-intelligence--a-new-module-name-for-already-specified-logic) |
| Agents | [`ENGINEERING_META_MODEL.md § 15`](../../ENGINEERING_META_MODEL.md#15-agent-ag) — per [`RUNTIME_ARCHITECTURE.md § 4.7`](RUNTIME_ARCHITECTURE.md#47-agents-module-vs-agent-ag-artifact-type) |

## 6. Adding a Future Module

Requires exactly one new manifest satisfying [§2](#2-the-module-manifest), implementing [§3](#3-the-module-lifecycle-interface)'s five hooks — no edit to any existing module, to the Runtime's own code, or to this document. "Without requiring runtime modification" ([RUNTIME must support future modules]) is this document's structural guarantee, not an aspiration: the Runtime has no closed list of module names anywhere in its own logic to update.
