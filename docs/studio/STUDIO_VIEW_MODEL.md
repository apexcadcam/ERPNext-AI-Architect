# STUDIO VIEW MODEL

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [STUDIO_ARCHITECTURE.md](STUDIO_ARCHITECTURE.md). The twelve **data projections** the Studio maintains, folded from [`STUDIO_EVENT_MODEL.md`](STUDIO_EVENT_MODEL.md)'s catalog.
**Scope:** Logical data shape only — what state each view holds and which events mutate it. **No screens, no layouts, no components.** "View Model" here is the CQRS/MVVM term for a read-side data contract, not a UI design.

---

## 0. The Shared Rule Every Projection Follows

A projection is a pure fold: `new_state = reduce(current_state, incoming_event)`. It has no other input — never a direct query to the module that produced the event, per [`STUDIO_ARCHITECTURE.md § 3`](STUDIO_ARCHITECTURE.md#3-the-architectural-pattern-cqrs-fully-committed). Every projection below is describable as "the events it's built from" plus "what it currently believes" — nothing more.

## 1. Runtime Lifecycle View

**Built from:** `RuntimeStateChanged`, `ModuleStateChanged`.
**Holds:** current Runtime process state (per [`LIFECYCLE.md § 1`](../runtime/LIFECYCLE.md#1-runtime-process-states)); per-module current state (per [`LIFECYCLE.md § 2`](../runtime/LIFECYCLE.md#2-module-states)) and time-in-state; a rolling history of the last N transitions per module, for "what just happened" recall without a full replay.

## 2. Pipeline Visualization

**Built from:** `PipelineRunStateChanged`, per-stage start/complete/retry events.
**Holds:** one entry per active or recent `pipeline_run_id`, each carrying: which [Pipeline Definition](../runtime/PIPELINE_ENGINE.md#4-existing-pipelines-as-pipeline-definitions) it is, current stage, stages completed vs. remaining (per [`LOGGING_AND_OBSERVABILITY.md § 6`](../runtime/LOGGING_AND_OBSERVABILITY.md#6-progress-reporting)'s existing progress shape), retry count per stage, and current run state (`Queued`/`Running`/`Failed`/`RollingBack`/etc., per [`LIFECYCLE.md § 4`](../runtime/LIFECYCLE.md#4-pipeline-run-states)).

## 3. Connector Status

**Built from:** `ConnectorStatusSnapshot`, `DocumentDiscovered`/`Downloaded`/`Parsed`.
**Holds:** one entry per registered [Source Connector](../crawler/SOURCE_CONNECTOR_SPEC.md), each carrying its declared identity/source-type ([`SOURCE_CONNECTOR_SPEC.md § 1.1`](../crawler/SOURCE_CONNECTOR_SPEC.md#11-identity)), current [`docs/crawler/OBSERVABILITY.md § 4`](../crawler/OBSERVABILITY.md#4-health-checks) health shape, and a rolling throughput counter (documents discovered/downloaded/parsed in the current window) — the Studio-side realization of that same document's [`§ 5`](../crawler/OBSERVABILITY.md#5-progress-reporting) progress-reporting shape, now continuously live rather than queried per run.

## 4. Knowledge Factory Status

**Built from:** `ArtifactCreated`, `ConflictDetected`, `ValidationCompleted`, `HumanApprovalRequested`/`Resolved`.
**Holds:** counts of artifacts produced per [type](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#2-artifact-types) in the current window; the current size of the [`KNOWLEDGE_VALIDATION_SPEC.md § 7`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate) pending-review queue (the single most operationally important number this view exposes — a growing queue is the earliest sign the human-in-the-loop gate is becoming a bottleneck); open vs. resolved [`Knowledge Conflict`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#27-knowledge-conflict) counts.

## 5. Knowledge Graph Visualization

**Built from:** `GraphSnapshot` (baseline), `GraphNodeCreated`/`GraphEdgeCreated` (incremental updates between snapshots).
**Holds:** node and edge counts by type, per [`KNOWLEDGE_GRAPH_SPEC.md § 3`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary)'s nine relationship types; growth rate over the current window. **Explicitly does not hold** a full traversable copy of the graph — rendering an actual graph visualization, if ever built, queries the real Knowledge Graph module through a read-only capability at render time (the one narrow, explicitly-justified exception to "events only," scoped solely to bulk graph-topology rendering where replaying every edge-creation event into an in-memory graph structure would be strictly worse than a direct read — noted here for honesty, not designed further, since it is implementation, not architecture).

## 6. Rule Engine Visualization

**Built from:** `RuleCandidateCreated`, `RuleEvaluated`.
**Holds:** count of proposals evaluated in the current window and their pass/fail/conflict outcome distribution; count of pending `Engineering Rule` candidate drafts awaiting the human-gated Architecture Review, per [`KNOWLEDGE_ARTIFACTS.md § 2.9`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#29-engineering-rule-candidate-not-a-pipeline-native-type) — the Studio never shows a candidate as anything other than pending review, since it cannot itself know whether a human has looked at it outside of an explicit event saying so.

## 7. Retrieval Activity

**Built from:** `RetrievalQueryExecuted`, `EmbeddingGenerated`.
**Holds:** query volume over the current window, distribution of result confidence bands ([`KNOWLEDGE_VALIDATION_SPEC.md § 8`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#8-confidence-scoring)), and embedding-generation throughput — the operational signal for whether [`RETRIEVAL_STRATEGY.md`](../knowledge-pipeline/RETRIEVAL_STRATEGY.md) is being exercised at all, and how confidently it's answering.

## 8. AI Agent Activity

**Built from:** `AgentInvoked`, `AgentCompleted`, `AgentFailed`.
**Holds:** currently-running Agent instances, per-Agent completion/failure rate over the current window. Per [`STUDIO_EVENT_MODEL.md`](STUDIO_EVENT_MODEL.md#ai-agent-activity)'s own scoping, this view shows *that* an Agent ran and *whether* it succeeded — never the Agent's internal reasoning or the Skills it composed, which remain that module's own concern entirely.

## 9. Version Intelligence

**Built from:** `VersionConflictFlagged`, `StalenessPropagated`, `BreakingChangeDetected`.
**Holds:** count of open version conflicts; count of artifacts currently marked `stale` (per [`KNOWLEDGE_REFRESH_POLICY.md § 3`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#3-staleness-propagation)'s cascade) and how far that staleness has propagated (how many dependent artifacts, per [`KNOWLEDGE_GRAPH_SPEC.md § 4`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules)'s `target-stale` annotation); a log of recent breaking-change escalations to human review, per [`KNOWLEDGE_REFRESH_POLICY.md § 4`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#4-breaking-change-propagation).

## 10. System Health

**Built from:** every module's `health_check()` result.
**Holds:** one entry per registered module: `{ module_id, healthy, detail, last_reported }` — a direct materialization of [`LOGGING_AND_OBSERVABILITY.md § 4`](../runtime/LOGGING_AND_OBSERVABILITY.md#4-health-checks), continuously updated rather than polled on demand the way `architect doctor` ([`CLI_ARCHITECTURE.md`](../runtime/CLI_ARCHITECTURE.md)) queries it.

## 11. Metrics

**Built from:** every module's declared metrics events.
**Holds:** whatever each module declared in its manifest ([`MODULE_SYSTEM.md § 2`](../runtime/MODULE_SYSTEM.md#2-the-module-manifest)) — this projection is intentionally generic and extensible: a future module's new metric requires no change to this document or to the Studio's own logic, only a new declared metric name the projection stores under, exactly mirroring [`MODULE_SYSTEM.md § 6`](../runtime/MODULE_SYSTEM.md#6-adding-a-future-module)'s "no runtime modification" guarantee one layer up, applied to the Studio's own extensibility.

## 12. Timeline

**Built from:** every event in [`STUDIO_EVENT_MODEL.md`](STUDIO_EVENT_MODEL.md)'s full catalog, per [`§ 3`](STUDIO_EVENT_MODEL.md#3-timeline-is-not-a-distinct-event-type) of that document.
**Holds:** an ordered sequence of events, filterable by any of the three correlation keys ([`LOGGING_AND_OBSERVABILITY.md § 2`](../runtime/LOGGING_AND_OBSERVABILITY.md#2-correlation)) — this is the one projection that is closest to a raw, unreduced event log rather than a folded summary, because its entire purpose is answering "show me everything that happened to this one document/run/artifact, in order," which a summarized projection would destroy the ability to answer.

---

## 13. Staleness Is a First-Class Property of Every Projection

Every one of the twelve views above carries its own `last_updated_at` and, where replay is in progress ([`STUDIO_INTEGRATION.md § 2`](STUDIO_INTEGRATION.md#2-integration-point-event-log-durability-and-replay)), a `catching_up: bool` flag — a view mid-replay is visibly marked as such, never presented as current when it isn't. This is the same "never silently present stale data as fresh" discipline already established for `stale`-flagged `Rule Metadata Record`s in [`RULE_METADATA_LIFECYCLE.md`](../ai-retrieval/RULE_METADATA_LIFECYCLE.md) and `target-stale`-annotated graph edges in [`KNOWLEDGE_GRAPH_SPEC.md § 4`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules) — applied here to the Studio's own eventual consistency, honestly represented rather than hidden.
