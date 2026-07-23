# STUDIO EVENT MODEL

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [STUDIO_ARCHITECTURE.md](STUDIO_ARCHITECTURE.md). The full catalog of events the Studio subscribes to, per [`EVENT_BUS.md § 2`](../runtime/EVENT_BUS.md#2-publish--subscribe)'s manifest-declared subscription mechanism.
**Scope:** Event types and their delivery policy. Not the resulting view state — see [`STUDIO_VIEW_MODEL.md`](STUDIO_VIEW_MODEL.md) for what each category of event is folded into.

---

## 1. Subscription Policy by Event Category

Per [`EVENT_BUS.md § 5`](../runtime/EVENT_BUS.md#5-backpressure)'s existing per-subscription overflow policy, never a single Studio-wide default:

| Category | Overflow policy | Why |
|---|---|---|
| State transitions (lifecycle, pipeline run completion, conflict detection, human-approval outcomes) | `block`-tolerant with a generous buffer, backed by replay ([`STUDIO_INTEGRATION.md § 2`](STUDIO_INTEGRATION.md#2-integration-point-event-log-durability-and-replay)) | A missed state transition would silently corrupt the view model's correctness — replay exists specifically so the Studio never has to choose between "block the bus" and "lose a state transition" |
| High-frequency telemetry (per-stage metrics ticks, per-request rate-limit budget updates) | `drop-oldest` | Losing an intermediate metrics sample is invisible to a human watching a dashboard; blocking the Bus over it would violate [`STUDIO_ARCHITECTURE.md § 4`](STUDIO_ARCHITECTURE.md#4-the-structural-passivity-guarantee)'s passivity guarantee for no real benefit |

This is the concrete mechanism behind "real-time" not meaning "guaranteed-complete": the Studio is allowed to miss a metrics sample and catch the next one; it is never allowed to miss a state transition, because replay exists precisely to prevent that without ever letting the Studio apply backpressure to real work.

## 2. Event Catalog

Every event below already has a semantic owner defined elsewhere in this project's frozen architecture, or is a narrow, clearly-labeled addition this document proposes where none existed. None represent new business logic — they represent the Studio's need to *observe* logic that already exists.

### Runtime Lifecycle

| Event | Published by | Meaning |
|---|---|---|
| `RuntimeStateChanged` | Runtime core | [`LIFECYCLE.md § 1`](../runtime/LIFECYCLE.md#1-runtime-process-states) transition — *new, per [`STUDIO_INTEGRATION.md § 3`](STUDIO_INTEGRATION.md#3-integration-point-lifecycle-transitions-as-events)* |
| `ModuleStateChanged` | Runtime core | [`LIFECYCLE.md § 2`](../runtime/LIFECYCLE.md#2-module-states) transition — *new, same integration point* |

### Pipeline Visualization

| Event | Published by | Meaning |
|---|---|---|
| `PipelineRunStateChanged` | Pipeline Engine | [`LIFECYCLE.md § 4`](../runtime/LIFECYCLE.md#4-pipeline-run-states) transition — *new, same integration point* |
| Per-stage start/complete/retry | Pipeline Engine | [`PIPELINE_ENGINE.md § 7`](../runtime/PIPELINE_ENGINE.md#7-metrics-and-tracing)'s existing metrics/tracing emission |

### Connector Status

| Event | Published by | Meaning |
|---|---|---|
| `DocumentDiscovered` / `DocumentDownloaded` / `DocumentParsed` | Crawler | [`CRAWLER_PIPELINE.md §§ 1,3,6`](../crawler/CRAWLER_PIPELINE.md#1-discover), unchanged |
| `MetadataExtracted` | Crawler | [`CRAWLER_PIPELINE.md § 7`](../crawler/CRAWLER_PIPELINE.md#7-extract-metadata), unchanged |
| `ConnectorStatusSnapshot` | Crawler | *New, periodic* — wraps [`docs/crawler/OBSERVABILITY.md § 4`](../crawler/OBSERVABILITY.md#4-health-checks)'s existing per-connector health record `{ reachable, credentials_valid, last_successful_crawl, consecutive_failures, circuit_state }`, published on the cadence [`CACHE_STRATEGY.md § 5`](../crawler/CACHE_STRATEGY.md#5-periodic-re-verification) already establishes, so a newly-connected Studio doesn't have to reconstruct connector health purely from years of individual document-level events |

### Knowledge Factory Status

*(Studio-level grouping term for Extraction → Pattern Extraction → Conflict Resolution → Validation — no new Runtime module.)*

| Event | Published by | Meaning |
|---|---|---|
| `ArtifactCreated` | Extractor | Any [content artifact](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#2-artifact-types) produced |
| `ConflictDetected` | Validator | [`KNOWLEDGE_VALIDATION_SPEC.md § 3`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#3-version-conflict-detection) |
| `ValidationCompleted` | Validator | The full eight-gate sequence finishing |
| `HumanApprovalRequested` / `HumanApprovalResolved` | Validator | [`KNOWLEDGE_VALIDATION_SPEC.md § 7`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate) entering/leaving the mandatory gate — *new, narrow addition; the gate itself is unchanged, this only makes its pending queue observable* |

### Knowledge Graph Visualization

| Event | Published by | Meaning |
|---|---|---|
| `GraphNodeCreated` / `GraphEdgeCreated` | Knowledge Graph | [`KNOWLEDGE_GRAPH_SPEC.md § 4`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#4-node-creation-and-update-rules) |
| `GraphSnapshot` | Knowledge Graph | *New, periodic* — a compact summary (node/edge counts by type, per [`KNOWLEDGE_GRAPH_SPEC.md § 3`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary)'s relationship vocabulary) so the Studio's graph view doesn't require replaying every edge ever created to know the graph's current shape |

### Rule Engine Visualization

| Event | Published by | Meaning |
|---|---|---|
| `RuleCandidateCreated` | Extractor / Rule Engine | [`KNOWLEDGE_ARTIFACTS.md § 2.9`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#29-engineering-rule-candidate-not-a-pipeline-native-type) |
| `RuleEvaluated` | Rule Engine | *New* — a proposal was checked against `rules/*.md`, per [`RUNTIME_ARCHITECTURE.md § 4.6`](../runtime/RUNTIME_ARCHITECTURE.md#46-rule-engine-module-vs-engineering-rule-artifact-type)'s module, carrying which rule(s) matched and the outcome |

### Retrieval Activity

| Event | Published by | Meaning |
|---|---|---|
| `RetrievalQueryExecuted` | Retrieval | *New* — a query ran, per [`RETRIEVAL_STRATEGY.md`](../knowledge-pipeline/RETRIEVAL_STRATEGY.md)'s filter→rank→conflict-handle→dependency-expand→reasoning-chain sequence, carrying the resulting artifact count and top-level confidence band |
| `EmbeddingGenerated` | Embedding | [`EMBEDDING_STRATEGY.md`](../knowledge-pipeline/EMBEDDING_STRATEGY.md) |

### AI Agent Activity

| Event | Published by | Meaning |
|---|---|---|
| `AgentInvoked` / `AgentCompleted` / `AgentFailed` | Agents | *New* — the Agents module's own execution lifecycle for an [`Agent (AG)`](../../ENGINEERING_META_MODEL.md#15-agent-ag) artifact instance; the Agents module's detailed internal behavior remains entirely its own, per [`RUNTIME_ARCHITECTURE.md § 4.7`](../runtime/RUNTIME_ARCHITECTURE.md#47-agents-module-vs-agent-ag-artifact-type) — these three events expose only that something ran, not how |

### Version Intelligence

| Event | Published by | Meaning |
|---|---|---|
| `VersionConflictFlagged` | Version Intelligence | [`KNOWLEDGE_CONFLICT_RESOLUTION.md § 2`](../knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md#2-two-documentation-versions-disagree) |
| `StalenessPropagated` | Version Intelligence | [`KNOWLEDGE_REFRESH_POLICY.md § 3`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#3-staleness-propagation) |
| `BreakingChangeDetected` | Version Intelligence | [`KNOWLEDGE_REFRESH_POLICY.md § 4`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#4-breaking-change-propagation) |

### System Health & Metrics

| Event | Published by | Meaning |
|---|---|---|
| Every module's `health_check()` result | Any module | [`LOGGING_AND_OBSERVABILITY.md § 4`](../runtime/LOGGING_AND_OBSERVABILITY.md#4-health-checks) |
| Every module's declared metrics | Any module | [`LOGGING_AND_OBSERVABILITY.md § 3`](../runtime/LOGGING_AND_OBSERVABILITY.md#3-metrics) |

## 3. Timeline Is Not a Distinct Event Type

"Timeline" (per the task's requirement list) is not a subscribed event category — it is a **derived view** built by ordering every event above by timestamp within a shared `correlation_id`, `pipeline_run_id`, or `artifact_id`, per [`LOGGING_AND_OBSERVABILITY.md § 2`](../runtime/LOGGING_AND_OBSERVABILITY.md#2-correlation)'s three correlation keys. See [`STUDIO_VIEW_MODEL.md § Timeline`](STUDIO_VIEW_MODEL.md#12-timeline) for the projection this document's full catalog feeds into.

## 4. What This Catalog Never Includes

No event here is a **command**. Every one is past-tense (`Created`, `Detected`, `Completed`, `Invoked`) — a statement that something already happened, never an instruction. A future event named in the imperative (`CrawlDocument`, `EvaluateRule`) would not belong on this list, because the Studio never publishes anything a domain module acts on, per [`STUDIO_ARCHITECTURE.md § 4`](STUDIO_ARCHITECTURE.md#4-the-structural-passivity-guarantee)'s `events_published` restriction.
