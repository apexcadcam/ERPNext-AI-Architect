# AI ARCHITECT STUDIO — ARCHITECTURE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](../runtime/RUNTIME_ARCHITECTURE.md). Introduces the Studio as one more [module](../runtime/MODULE_SYSTEM.md), governed by the exact same contract as Crawler, Extractor, Validator, or any other — nothing about the Module System, Plugin Registry, or Event Bus changes to accommodate it.
**Scope:** What the Studio *is*, architecturally, and why it can never become load-bearing. Not a UI design — no screens, no components, no HTML/React/Vue. That implementation is explicitly deferred; see [§7](#7-what-happens-next-explicitly-out-of-scope-here).

---

## 1. What the Studio Is

A **real-time Engineering Intelligence Dashboard** — a live, continuously-updated projection of everything the Runtime and its modules are doing, built entirely by observing the [Event Bus](../runtime/EVENT_BUS.md). It is not an administration panel (it issues no commands), not a CRUD interface (it owns no records anything else depends on), and not a monitoring afterthought bolted onto existing modules — it is a first-class, permanent module whose entire purpose is to make the rest of the system *legible*, in real time, to a human watching it.

## 2. What the Studio Is Not

Stated as plainly as the task itself states it, because this is the one property every other document in this set exists to protect:

- It does not invoke a Crawler, a Connector, a Parser, an Extractor, a Validator, the Rule Engine, or an Agent.
- It does not issue commands. It has no write path into any module's behavior.
- It does not own business logic. Every fact it displays is a fact some other module already asserted, via an event.
- It is not the system of record for anything. If the Studio disappeared entirely, nothing else in the Runtime would notice or behave differently.

## 3. The Architectural Pattern: CQRS, Fully Committed

The Studio is an **event-sourced read model** in the Command Query Responsibility Segregation sense: every module that does real work is the *write side* (it changes state, and announces that it did so via an event); the Studio is *purely* the *read side* — it never issues a command, and its own internal state (its "view model," see [`STUDIO_VIEW_MODEL.md`](STUDIO_VIEW_MODEL.md)) is nothing more than a materialized fold over the events it has observed. This is not a metaphor chosen for convenience — it is the literal mechanism that makes "the Studio must never control anything" true structurally rather than by policy, per [§4](#4-the-structural-passivity-guarantee).

## 4. The Structural Passivity Guarantee

The Studio's [module manifest](../runtime/MODULE_SYSTEM.md#2-the-module-manifest) declares:

- **`capabilities_provided: []`** — empty, always. Per [`PLUGIN_REGISTRY.md § 4`](../runtime/PLUGIN_REGISTRY.md#4-dependency-validation), a module's `capabilities_required` is only ever satisfied by another enabled module's `capabilities_provided`. If the Studio provides nothing, **no module can ever be validated as depending on it** — this is not a convention the Studio's authors promise to honor, it is a fact the existing Plugin Registry's dependency-validation algorithm enforces mechanically, on every boot, for free. The Runtime remaining fully functional with the Studio disabled is therefore true by construction, permanently — not merely true today because nobody happened to add a dependency on it yet.
- **`capabilities_required`** — contains only infrastructure capabilities every module is entitled to (its own [Storage](../runtime/STORAGE_ABSTRACTION.md) namespace, [Logging](../runtime/LOGGING_AND_OBSERVABILITY.md)) and **never** a capability belonging to Crawler, Parser, Extractor, Validator, Knowledge Graph, Embedding, Retrieval, Rule Engine, Version Intelligence, or Agents. [`PLUGIN_REGISTRY.md § 4`](../runtime/PLUGIN_REGISTRY.md#4-dependency-validation)'s existing validation is the enforcement point — a future accidental addition of a domain capability to the Studio's manifest fails boot-time validation the same way any other unauthorized dependency would, per [`MODULE_SYSTEM.md § 4`](../runtime/MODULE_SYSTEM.md#4-module-isolation)'s isolation rule.
- **`pipeline_stage_bindings: []`** — the Studio implements no [Pipeline Definition](../runtime/PIPELINE_ENGINE.md#1-a-pipeline-definition-is-data-not-code) stage. It is never in the critical path of a crawl, an extraction, a validation pass, or anything else — a Studio failure cannot stall a pipeline it was never a stage of.
- **`events_subscribed`** — broad, per [`STUDIO_EVENT_MODEL.md`](STUDIO_EVENT_MODEL.md). This is the Studio's *only* channel of information about the rest of the system.
- **`events_published`** — limited to Studio-internal events (e.g., a push-update signal to its own connected clients), never an event any domain module subscribes to. The Studio cannot influence pipeline behavior even by accident, because nothing downstream is listening to it.

## 5. Why No New ADR, and No Redesign

Per the task's own instruction — preserve every ADR and the Architecture Freeze; document integration points rather than redesign. Nothing here adds a Knowledge Artifact type, renames an existing one, or forces a contested choice — the Studio fits the existing [`MODULE_SYSTEM.md`](../runtime/MODULE_SYSTEM.md) contract without modification, which is itself evidence the Runtime's design was already general enough to absorb this. Two narrow, additive clarifications surface from the Studio's needs, documented in [`STUDIO_INTEGRATION.md § 2`](STUDIO_INTEGRATION.md#2-integration-point-event-log-durability-and-replay) and [`§ 3`](STUDIO_INTEGRATION.md#3-integration-point-lifecycle-transitions-as-events) — neither contradicts anything [`EVENT_BUS.md`](../runtime/EVENT_BUS.md) or [`LIFECYCLE.md`](../runtime/LIFECYCLE.md) already states; both fill in something those documents left silent.

## 6. Document Map

| Document | Answers |
|---|---|
| [STUDIO_ARCHITECTURE.md](STUDIO_ARCHITECTURE.md) | This document. |
| [STUDIO_INTEGRATION.md](STUDIO_INTEGRATION.md) | How does the Studio actually wire into the Runtime — boot, storage, the two integration-point clarifications? |
| [STUDIO_EVENT_MODEL.md](STUDIO_EVENT_MODEL.md) | What events does it subscribe to, and with what delivery guarantees? |
| [STUDIO_VIEW_MODEL.md](STUDIO_VIEW_MODEL.md) | What does each of the twelve required views actually contain, as data — not as a screen? |

## 7. What Happens Next (Explicitly Out of Scope Here)

No screen has been designed. No component library, frontend framework, or wire protocol to a browser has been chosen. Those are implementation decisions for a much later phase, gated by the same Architecture Review discipline already applied to every prior round in this project.
