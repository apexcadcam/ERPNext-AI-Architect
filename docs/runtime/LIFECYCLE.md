# LIFECYCLE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md).
**Scope:** Three state machines — the Runtime process itself, a Module, and a Pipeline Run. Not a redefinition of any knowledge-artifact lifecycle already frozen elsewhere ([`docs/ai-retrieval/RULE_METADATA_LIFECYCLE.md`](../ai-retrieval/RULE_METADATA_LIFECYCLE.md), [`docs/knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md)'s staleness states) — those remain exactly as specified.

---

## 1. Runtime Process States

```
Starting → PluginDiscovery → DependencyValidation → ConfigLoading →
PipelineRegistration → ConnectorRegistration → HealthChecking → Ready
                                                                    │
                                                                    ▼
                                                              Running ──▶ Draining ──▶ Stopped
                                                                    │
                                                                    ▼
                                                                 Failed
```

Full detail per state: [`RUNTIME_BOOT_SEQUENCE.md`](RUNTIME_BOOT_SEQUENCE.md). `Ready` is the state [`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md) commands (other than `architect runtime start` itself and `architect doctor`, which can run in a degraded state to diagnose why `Ready` wasn't reached) require before accepting work.

## 2. Module States

```
Registered → Validated → Initialized → Started → Running
                 │                                   │
                 ▼                                   ▼
              Failed                             Stopping → Stopped
                                                       │
                                                       ▼
                                                  (restart) → Initialized
```

- **Registered**: [`PLUGIN_REGISTRY.md § 2`](PLUGIN_REGISTRY.md#2-registration), manifest read, nothing executed.
- **Validated**: passed [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation)'s three checks.
- **Initialized**: `init(container)` returned successfully — dependencies resolved, internal state constructed, per [`MODULE_SYSTEM.md § 3`](MODULE_SYSTEM.md#3-the-module-lifecycle-interface).
- **Started / Running**: `start()` returned; the module is actively serving its declared capabilities and processing subscribed events.
- **Stopping / Stopped**: `stop()` invoked and returned — guaranteed-called, per [§3](#3-shutdown-ordering).
- **Failed**: any hook threw or returned an error state; a `Failed` module is excluded from [`PLUGIN_REGISTRY.md § 5`](PLUGIN_REGISTRY.md#5-capability-discovery)'s capability graph until it successfully restarts, and anything depending on its capabilities is itself flagged degraded rather than silently proceeding as if the dependency were healthy.

A **restart** re-enters at `Initialized`, not `Registered` — the manifest and its validation result don't change on restart, only the module's own runtime state does.

## 3. Shutdown Ordering

Modules stop in **reverse dependency order** — a module is never stopped while something still depending on its capabilities is still `Running`, mirroring [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation)'s dependency graph, walked backward. `Draining` (the Runtime-level state, [§1](#1-runtime-process-states)) means: stop accepting new pipeline runs and CLI commands, allow in-flight pipeline runs to reach a stage boundary (never interrupted mid-stage, per [`PIPELINE_ENGINE.md § 2`](PIPELINE_ENGINE.md#2-stage-execution-contract)'s atomic stage-invocation contract), then proceed to per-module shutdown in the order above.

## 4. Pipeline Run States

```
Queued → Running → Completed
             │
             ├──▶ Failed ──▶ RollingBack ──▶ RolledBack
             │
             └──▶ Cancelled ──▶ RollingBack ──▶ RolledBack
```

- **Running**: stages execute per [`PIPELINE_ENGINE.md § 1`](PIPELINE_ENGINE.md#1-a-pipeline-definition-is-data-not-code)'s declared sequence; a stage's own retry ([`PIPELINE_ENGINE.md § 5`](PIPELINE_ENGINE.md#5-retries)) happens *within* this state, never producing a separate visible run-state transition per retry attempt.
- **Failed**: a stage exhausted its retries or reported an unretryable [`ERROR_HANDLING.md`](../crawler/ERROR_HANDLING.md) category.
- **RollingBack / RolledBack**: [`PIPELINE_ENGINE.md § 6`](PIPELINE_ENGINE.md#6-rollback)'s compensating-action walk — never a state that deletes what was already produced, only marks it `rolled_back`.
- **Cancelled**: an explicit, human- or CLI-triggered stop of an in-flight run, distinct from `Failed` because nothing about the pipeline's own execution went wrong — it was told to stop.

## 5. What This Document Deliberately Does Not Cover

`Engineering Rule` status (`Draft`/`Review`/`Stable`/`Deprecated`), `RM` sync state (`generated`/`validated`/`synced`/`stale`), and `Knowledge Document` staleness — every one of these remains owned by its own already-frozen lifecycle document. A pipeline run reaching `Completed` for a `knowledge.validation` run, for instance, is a Runtime-level fact about that *execution*; it is not the same fact as, and never directly sets, an artifact's own `confidence` or `status` field — those are written by the Validator module's own logic, per [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md), using the Runtime only as the substrate it ran on.
