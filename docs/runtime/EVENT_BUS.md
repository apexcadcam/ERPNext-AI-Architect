# EVENT BUS

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md § 4.2](RUNTIME_ARCHITECTURE.md#42-crawler_pipelinemd--9s-emit-pipeline-event-and-the-event-bus). The concrete transport [`CRAWLER_PIPELINE.md § 9`](../crawler/CRAWLER_PIPELINE.md#9-emit-pipeline-event)'s "Emit Pipeline Event" was always describing abstractly.
**Scope:** Generic publish/subscribe routing. The Runtime routes events; it never interprets them.

---

## 1. The Bus Knows Topics, Not Meaning

An event is `{ event_type, payload, emitted_by, correlation_id, pipeline_run_id, timestamp }`. The Bus routes by `event_type` string match against subscriptions — it never inspects `payload`, never validates it against a schema (that's the subscribing module's own responsibility, using whatever schema its manifest declares for that event type per [`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest)), and never assigns meaning to an event type's name. `DocumentDiscovered` is, to the Bus, an opaque string identical in kind to any future module's invented event name — the Bus's job ends at delivery.

## 2. Publish / Subscribe

A module declares `events_published` and `events_subscribed` in its manifest ([`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest)); the Bus wires subscriptions to publications by `event_type` match at [`RUNTIME_BOOT_SEQUENCE.md § 5`](RUNTIME_BOOT_SEQUENCE.md#5-pipeline-registration)'s registration step, not dynamically discovered at publish time — a module publishing an event type nothing subscribes to is a valid, unremarkable state (not every event needs a listener), but a module subscribing to an event type nothing publishes is flagged during [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation)-style validation as a likely configuration error.

## 3. Delivery Guarantees

**At-least-once, per-correlation-id-ordered.** A single event may be delivered more than once under failure conditions (a subscriber crashing mid-processing), so every subscriber's handler must be idempotent with respect to its own event type — the same discipline [`STORAGE_LAYOUT.md § 2`](../crawler/STORAGE_LAYOUT.md#2-path-structure)'s content-addressed writes already assume for storage, applied here to event handling. Ordering is guaranteed only *within* a single `correlation_id`'s event stream (the events belonging to one Crawl Item's, or one artifact's, journey through the system arrive in emission order); no ordering guarantee exists *across* different correlation IDs, which is what permits [`PIPELINE_ENGINE.md § 8`](PIPELINE_ENGINE.md#8-parallel-and-future-distributed-execution)'s parallel execution without the Bus becoming a serialization bottleneck.

## 4. Example Event Types, Mapped to Their Owning Module

The Bus doesn't know this table — it exists only to show that every example event the task names already has a real, frozen semantic owner, not a new one invented here:

| Event type | Emitted by | Corresponds to |
|---|---|---|
| `DocumentDiscovered` | Crawler | [`CRAWLER_PIPELINE.md § 1`](../crawler/CRAWLER_PIPELINE.md#1-discover) |
| `DocumentDownloaded` | Crawler | [`CRAWLER_PIPELINE.md § 3`](../crawler/CRAWLER_PIPELINE.md#3-download) |
| `DocumentParsed` | Crawler | [`CRAWLER_PIPELINE.md § 6`](../crawler/CRAWLER_PIPELINE.md#6-parse) |
| `MetadataExtracted` | Crawler | [`CRAWLER_PIPELINE.md § 7`](../crawler/CRAWLER_PIPELINE.md#7-extract-metadata) — document-level metadata, **not** knowledge-claim extraction (see next row) |
| `ArtifactCreated` | Extractor | Any [`Knowledge API`/`Pattern`/`Best Practice`/`Example`/`Workflow`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#2-artifact-types) instance produced |
| `ConflictDetected` | Validator | A [`Knowledge Conflict`](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#27-knowledge-conflict) created, per [`KNOWLEDGE_VALIDATION_SPEC.md § 3`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#3-version-conflict-detection) |
| `ValidationCompleted` | Validator | The full [`KNOWLEDGE_VALIDATION_SPEC.md`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md) eight-gate sequence finishing, pass or fail |
| `EmbeddingGenerated` | Embedding | [`EMBEDDING_STRATEGY.md`](../knowledge-pipeline/EMBEDDING_STRATEGY.md) |
| `RuleCandidateCreated` | Extractor / Rule Engine | An [`Engineering Rule` candidate draft](../knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#29-engineering-rule-candidate-not-a-pipeline-native-type) — publishing this event is what triggers [`KNOWLEDGE_VALIDATION_SPEC.md § 7`](../knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate)'s mandatory human review path, never an automated `Stable` transition |

`Emit Pipeline Event` from [`CRAWLER_PIPELINE.md § 9`](../crawler/CRAWLER_PIPELINE.md#9-emit-pipeline-event) is, concretely, publishing a `DocumentPersisted`-shaped event to this Bus — no change to what that section says the event contains, only a name for the mechanism it always assumed existed.

## 5. Backpressure

A publisher whose subscribers cannot keep pace does not block indefinitely nor silently drop events — the Bus applies a bounded queue per subscription with an explicit overflow policy (declared per subscription: `block` for subscribers where losing an event is unacceptable, e.g., anything feeding [`ValidationCompleted`](#4-example-event-types-mapped-to-their-owning-module)'s downstream persistence; `drop-oldest` for high-volume, loss-tolerant telemetry-style events) — the choice is a per-subscription configuration decision, never a Bus-wide default silently applied everywhere.

## 6. Scale

At millions of events (matching [`RUNTIME_ARCHITECTURE.md § 7`](RUNTIME_ARCHITECTURE.md#7-non-functional-requirements-at-scale)'s "millions of artifacts"), the Bus's topic-based routing and per-correlation-id ordering (not global ordering) are what keep this from becoming a single serialization point — the same reasoning already applied to [`RATE_LIMITING.md § 1`](../crawler/RATE_LIMITING.md#1-three-budgets-checked-in-order)'s per-host/per-connector budget independence, generalized to event delivery.
