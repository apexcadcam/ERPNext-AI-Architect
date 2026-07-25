# Sprint 6 Release Notes — Runtime Integration / Composition Root

**Release:** `v0.7.0-runtime-integration`
**Status:** Approved — all seven phases passed architecture and implementation review; implementation frozen
**Branch:** `review/sprint6-runtime-integration` → merged into `main`
**Depends on (frozen, unmodified except where noted):** Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer, Sprint 4 Planning Engine, Sprint 5 Execution Engine (`v0.6.0-execution-engine`), `ADR-0009`, `ADR-0014`

---

## Summary

Sprint 6 wires the Planning Engine (Sprint 4) and the Execution Engine (Sprint 5) into the real Runtime (Sprint 1) as first-class Modules, resolvable through the ordinary Container by any future caller — exactly the same way Integration already was. It also closes two real gaps that existed before this Sprint began: a capability-registration ordering defect that already, silently affected every currently shipped domain module (not merely this Sprint's own new ones), and `ADR-0009`'s three-Sprint-old, explicitly disclosed `connector_search_paths` wiring gap. A third, long-deferred question — `ExecutionContext.event_bus` — was finally resolved, closing a gap disclosed at every phase of Sprint 5 since Phase 3. Every phase was implemented against the approved Sprint 6 Architecture Package and its three approved ADR Candidates, each independently reviewed before implementation began.

## What Shipped

### ADR Candidate A — Capability-Registration Ordering Fix (`runtime/boot.py`, Phase 1)

`_start_one_module()`'s generic per-module capability-registration loop ran unconditionally after a module's own `init()`, silently overwriting any capability that `init()` had already registered more specifically. Confirmed to already affect every domain module shipped before this Sprint — Integration (`integration.connector_registry`), Extractor (`knowledge.extract` and two others), Validator (all eight `knowledge.validate.*` capabilities) — never caught by any existing test. Fixed with a two-line guard using `Container.is_registered()`; the generic fallback's own legitimate use case (a module that registers nothing) is unchanged.

### ADR Candidate B — `runtime.event_bus` / `runtime.config` Capabilities (`runtime/boot.py`, Phase 2)

Two well-known, Container-resolvable Runtime infrastructure capabilities, registered unconditionally at `Runtime` construction, before any module's `init()` runs. `"runtime.event_bus"` was already referenced, defensively, by `knowledge/extraction/module.py` and `knowledge/validation/module.py`, predating this Sprint — this is the first place anything actually registers it. Neither capability is declared in any module's manifest; both are Runtime infrastructure, evaluated against a new, explicit four-part qualification test (unconditional Runtime-owned existence, domain-agnosticism, no other channel plus demonstrated need, safety) recorded as a standing architectural invariant for future extensions.

### Configuration-Driven `connector_search_paths` (`integration/module.py`, Phase 3)

Closes `ADR-0009`'s own long-named wiring gap, generically, via `runtime.config` — no special-casing of Integration by name anywhere in `runtime/boot.py`. A value already set by hand always takes priority and is never silently overridden; with no `runtime.config` registered at all, behavior is identical to every prior Sprint. Closes `tests/sprint3/test_smoke.py`'s own three-Sprint-old, explicitly disclosed limitation.

### ADR Candidate C — `ExecutionContext.event_bus` (`execution/context.py`, `execution/engine.py`, Phase 4)

An optional, additive `event_bus: EventBus | None = None` field, and all nine identifiers `execution/events.py` has named and payload-specified since Sprint 5 Phase 2, now firing from their documented points in `ExecutionEngine.execute()`'s existing loop. `ExecutionEngine` treats `context.event_bus` as a publish-only collaboration — enforced by a dedicated AST test, not a new `Protocol` — and every publish is wrapped so a delivery failure can never affect a run's own outcome, extending Sprint 5's best-effort execution philosophy to this integration point. Every pre-Sprint-6 `ExecutionContext` construction remains valid unchanged.

### `PlanningModule` (`planning/module.py`, `plugins/planning/`, Phase 5)

Hosts a ready-to-use `PlanningEngine`, with `RuleBasedPlannerStrategy` registered in `init()`, provides `planning.engine`, requires nothing — restating `ADR-0011`'s one-way dependency rule at the module level.

### `ExecutionModule` (`execution/module.py`, `plugins/execution/`, Phase 6)

Hosts a ready-to-use `ExecutionEngine`, constructed exactly per `ADR-0014`: `RetryPolicy(registry)` first, then `ExecutionEngine(retry_policy)`. Provides `execution.engine`, requires exactly `integration.connector_registry` — a real, Container-validated dependency edge onto `IntegrationModule`. Owns only the `ExecutionEngine`; never constructs an `ExecutionContext`, never touches `event_bus`, never imports `planning/`.

## Architecture Validation

Phase 7's final validation exercised the complete, frozen Phase 1–6 implementation as one unit:

- **Capability registration** — a real `Runtime.boot()` with Integration, Planning, and Execution all enabled proves every one of `integration.connector_registry`/`planning.engine`/`execution.engine`/`runtime.event_bus`/`runtime.config` resolves to the correct concrete object, none shadowed — the direct, full-system proof that Phase 1's fix holds, not merely that boot doesn't raise.
- **End-to-end flow** — a real `Goal → PlanningEngine.create_plan() → ExecutionEngine.execute()` chain, entirely through Container resolution rather than by-hand construction, against the real Filesystem connector.
- **Event observability** — a subscriber registered on the real `runtime.event_bus` before a real run proves real events genuinely arrive through the real `EventBus`, the full-system counterpart to Phase 4's own unit-level proof.
- **Architecture boundaries** — `planning/module.py`/`execution/module.py` introduce no forbidden import; `runtime/` still has no direct or transitive import of `planning/`/`execution/` anywhere in its own package, preserving `MODULE_SYSTEM.md §1`'s "the Runtime never special-cases a module by name" invariant throughout.

## Full Regression Validation

- **779/779 tests passing**
- **`mypy --strict` clean**
- **`ruff check` clean**
- **`ruff format` clean**

Two issues were found and fixed during Phase 7's own validation work, both disclosed in that phase's report: a boundary-test assertion that incorrectly expected `planning` absent from a transitive import chain that legitimately, unavoidably includes it (corrected to assert the one claim that's actually true — `planning.module`, the live Module wrapper, is never transitively reached); and two end-to-end tests that initially read/wrote real files at the process's actual working directory rather than an isolated `tmp_path`, fixed with a small connector-repointing helper mirroring an already-established pattern from `tests/execution/test_connector_invoker.py`. No production code changed as a result of Phase 7.

## Explicitly Out of Scope

Named here, not silently assumed solved: configuration-driven `PlannerStrategy` selection (only one strategy exists to select between); `CapabilityResolver` (Planning's `available_capabilities` remains hand-assembled by whoever calls `create_plan()`); the Agent Orchestration Loop (nothing in this Sprint calls `execute()` or assembles a real `ExecutionContext` on its own authority — this Sprint makes the two engines *reachable*, not *invoked*); wiring Planning's own event identifiers (`planning/events.py` remains unpublished); `ADR-0009`'s C2 (the credential-injection seam, still unresolved); and a manifest-declared-vs-runtime-registered capability consistency check (a real observation raised during architecture review, named as a Future ADR Candidate, not designed here). None of these were implemented in Sprint 6.
