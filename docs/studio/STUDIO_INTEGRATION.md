# STUDIO INTEGRATION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [STUDIO_ARCHITECTURE.md](STUDIO_ARCHITECTURE.md). How the Studio module actually wires into the Runtime, and the two integration-point clarifications its requirements surface.
**Scope:** Boot sequence participation, storage, and the Event Bus/Lifecycle extensions. No code.

---

## 1. Boot Sequence Participation — No Special-Casing Required

The Studio registers, is discovered, is dependency-validated, is configured, and starts exactly per [`RUNTIME_BOOT_SEQUENCE.md`](../runtime/RUNTIME_BOOT_SEQUENCE.md)'s eight steps, with nothing added or skipped:

| Boot step | Studio's participation |
|---|---|
| 2. Plugin Discovery | Manifest read like any module's. |
| 3. Dependency Validation | Trivially passes — `capabilities_required` names only infrastructure, `capabilities_provided` is empty, so it can neither be an unsatisfied dependency nor a cycle participant. |
| 5. Pipeline Registration | No stage bindings to register — this step is a no-op for the Studio. |
| 6. Connector Registration | Not applicable — the Studio hosts no nested plugin system. |
| 7. Health Checks | Reports its own `health_check()` (per [`MODULE_SYSTEM.md § 3`](../runtime/MODULE_SYSTEM.md#3-the-module-lifecycle-interface)) — whether it's successfully connected to the Event Bus and how far behind its view model currently is, per [`STUDIO_VIEW_MODEL.md § 13`](STUDIO_VIEW_MODEL.md#13-staleness-is-a-first-class-property-of-every-projection). A Studio reporting unhealthy here **never blocks Runtime boot** — it is always configured optional, per [`RUNTIME_BOOT_SEQUENCE.md § 7`](../runtime/RUNTIME_BOOT_SEQUENCE.md#7-health-checks)'s existing allowance for non-critical modules. |

That the Studio needs *zero* new boot-sequence logic is itself the strongest evidence [`MODULE_SYSTEM.md`](../runtime/MODULE_SYSTEM.md)'s contract was general enough — a module with almost no dependencies and a purely observational role still fits the identical lifecycle every domain module fits.

## 2. Integration Point: Event Log Durability and Replay

**The gap:** [`EVENT_BUS.md`](../runtime/EVENT_BUS.md) specifies delivery guarantees (at-least-once, per-correlation-id ordering, bounded per-subscription queues) but is silent on whether events are retained anywhere past delivery. A Studio that starts *after* the Runtime has been running — or reconnects after a restart — needs a way to reconstruct current state without ever directly querying a module, per [`STUDIO_ARCHITECTURE.md § 2`](STUDIO_ARCHITECTURE.md#2-what-the-studio-is-not). Nothing in `EVENT_BUS.md` currently provides this.

**Resolution — additive, not contradictory:** the Event Bus maintains a durable, append-only log of every published event, and supports **replay** — a subscriber may request delivery starting from a specific point (from the beginning, or from a previously-recorded checkpoint) rather than only from "now." This does not change [`EVENT_BUS.md § 1`](../runtime/EVENT_BUS.md#1-the-bus-knows-topics-not-meaning)'s "routes by topic, never interprets payload" rule, [`§ 3`](../runtime/EVENT_BUS.md#3-delivery-guarantees)'s at-least-once/idempotent-handler requirement, or [`§ 5`](../runtime/EVENT_BUS.md#5-backpressure)'s per-subscription overflow policy — it adds a durability property to the transport those sections already assumed something like it could have, without requiring any of them to be rewritten. Every existing consumer of the Bus (Crawler, Validator, etc.) is unaffected — they still consume events forward from "now" and never need to replay.

**Checkpointing:** the Studio persists its own last-processed event position (per event type or globally) to its own storage namespace ([§4](#4-storage)), so a restart resumes replay from that checkpoint rather than from the beginning of time — the same checkpoint-and-resume shape [`CACHE_STRATEGY.md § 4`](../crawler/CACHE_STRATEGY.md#4-resuming-an-interrupted-crawl) already established for interrupted crawls, applied here to event consumption instead of document acquisition.

## 3. Integration Point: Lifecycle Transitions as Events

**The gap:** [`LIFECYCLE.md`](../runtime/LIFECYCLE.md) defines three state machines (Runtime process, Module, Pipeline Run) but does not explicitly say every transition publishes an event — "Runtime lifecycle visibility" and "Connector status" both require the Studio to observe these transitions, and it can only ever observe events.

**Resolution:** every state transition in all three of `LIFECYCLE.md`'s state machines publishes a corresponding event — `RuntimeStateChanged`, `ModuleStateChanged`, `PipelineRunStateChanged` — carrying the prior state, new state, and timestamp. This adds nothing to what `LIFECYCLE.md` says the states *are* or *when* transitions happen; it only names the mechanism by which an already-happening transition becomes observable off the process that made it, exactly the same shape as [`RUNTIME_ARCHITECTURE.md § 4.2`](../runtime/RUNTIME_ARCHITECTURE.md#42-crawler_pipelinemd--9s-emit-pipeline-event-and-the-event-bus)'s earlier reconciliation of `CRAWLER_PIPELINE.md`'s "Emit Pipeline Event" with the Event Bus.

## 4. Storage

The Studio persists its own materialized view model ([`STUDIO_VIEW_MODEL.md`](STUDIO_VIEW_MODEL.md)) and event-replay checkpoint to its own dedicated namespace via the standard [`STORAGE_ABSTRACTION.md § 1`](../runtime/STORAGE_ABSTRACTION.md#1-namespaces-not-paths) contract — the same `read`/`write`/`exists`/`list` operations any module uses, scoped to a namespace (e.g., `studio_view`) no other module ever writes to or reads from. The Studio **never** reads from `raw/`, `documents/`, or `cache/` ([`STORAGE_LAYOUT.md § 1`](../crawler/STORAGE_LAYOUT.md#1-three-zones-three-different-durability-guarantees)) or any other module's namespace directly — everything it knows about those zones' contents, it learned from an event, never from a direct read. This namespace is itself fully disposable: deleting it and replaying the event log from the beginning reconstructs it exactly, the same "cache is never a source of truth" property [`CACHE_STRATEGY.md § 6`](../crawler/CACHE_STRATEGY.md#6-cache-is-never-a-source-of-truth) already established, applied here to the Studio's entire persisted state.

## 5. Configuration

The Studio's own tunables (which event categories to subscribe to at full fidelity vs. sampled, how far back to retain its own view history, its Event Bus checkpoint interval) live at the Module layer of [`CONFIGURATION_SYSTEM.md § 2`](../runtime/CONFIGURATION_SYSTEM.md#2-the-six-layers) — no new configuration layer is introduced.

## 6. CLI Surface

Not designed here (out of this document's scope) but requires no change to [`CLI_ARCHITECTURE.md`](../runtime/CLI_ARCHITECTURE.md) — a future read-only `architect studio status` command is exactly what [`CLI_ARCHITECTURE.md § 6`](../runtime/CLI_ARCHITECTURE.md#6-future-growth)'s existing `cli_bindings`-in-manifest mechanism already supports, without editing the CLI's own dispatch logic.
