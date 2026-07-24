# Sprint 5 Release Notes — Execution Engine

**Release:** `v0.6.0-execution-engine`
**Status:** Approved — all seven phases passed architecture review; implementation frozen
**Branch:** `review/sprint5-execution-engine` → merged into `main`
**Depends on (frozen, unmodified except where noted):** Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer & Knowledge Graph, Sprint 4 Planning Engine (`v0.5.0-planning-engine`)

---

## Summary

Sprint 5 delivers the Execution Engine: given a validated `Plan` (Sprint 4) and an `ExecutionContext`, it runs the Plan's steps to completion against real connectors — and nothing more. It does not plan, does not reason, does not create or modify a `Plan`, and depends on Planning in one direction only. Every phase was implemented against the approved Sprint 5 Architecture Package, with two genuine architectural gaps surfaced by implementation, resolved through explicit clarification before continuing, and recorded permanently as ADR-0014 — never silently decided mid-implementation. The final validation phase (Phase 7) confirmed the whole package holds together as one coherent unit, extending Planning's own output into a real, working execution against the real Filesystem connector, with zero bugs found and zero unplanned production changes required.

## What Shipped

### Connector Invocation Completion (`integration/`, Phase 1)

The one place this Sprint touches a frozen Sprint 3 file, exactly as `ADR-0009` named as a precondition: `ConnectorRequest`/`ConnectorResponse` (the envelope `SPRINT3_ARCHITECTURE_PACKAGE.md §6.2` designed but never built) and `ConnectorLifecycle.invoke(request) -> ConnectorResponse`, a new abstract method every connector must implement. The Filesystem Connector gained a centralized dispatch-table `invoke()` covering all four of its existing operations. `integration/events.py` gained the `ConnectorInvoked`/`Succeeded`/`Failed` identifiers named by `ADR-0009`'s M3 finding — publication itself deferred to Execution's own `ConnectorInvoker`.

### Execution Core Models & State (`execution/{contract,lifecycle,errors,events}.py`, Phase 2)

`ExecutionRun` (a plain, mutable dataclass — the one place this Sprint's own "no mutation" discipline differs from Planning's frozen inputs, mirroring `runtime.boot.RuntimeInfo`'s own live-orchestration-state precedent), `StepExecutionRecord`, `ExecutionResult`, and `RollbackOutcome` (frozen pydantic). Two state machines reusing `runtime.lifecycle.StateMachine` a fourth time: `ExecutionRunState` and `StepExecutionState` — the latter with no independent `CANCELLED` value, folding cancellation-before-start into `SKIPPED` alongside an unmet dependency and a denied confirmation, per the Architecture Review's own accepted correction. The `ExecutionError_` hierarchy, with `PlanNotExecutableError` narrowed, after a disclosed follow-up correction during review, to a genuine engine-internal precondition signal — never used for ordinary capability-availability failures.

### Read/Invoke-Only Input Surface (`execution/{context,connector_invoker,confirmation,rollback,cancellation,scheduler}.py`, Phase 3)

`ExecutionContext` — the Executor's complete, read-only input bundle, deliberately carrying no `GraphReader` (every fact the Knowledge Graph contributed already went into the `Plan` at planning time). `ConnectorInvoker`, a narrow structural `Protocol` mirroring `planning.graph_reader.GraphReader`'s exact narrowing shape, with `RegistryConnectorInvoker` as the one concrete implementation. `ConfirmationProvider` and `RollbackStrategy`, each a one-method `ABC` with a safe reference default (`DenyAllConfirmationProvider`, `UnsupportedRollbackStrategy`). `CancellationToken`, a small cooperative flag. `StepScheduler`, a stable topological sort keyed by original `Plan.steps` index — never a `set`'s iteration order — per the Architecture Review's own added Scheduling Tie-Breaking rule.

### Confirmation Gate & Retry Policy (`execution/{confirmation_gate,retry}.py`, Phase 4)

`ConfirmationGate` — never consults its `ConfirmationProvider` at all for a step that doesn't require confirmation. `RetryPolicy` — re-resolves a step's `idempotent`/`max_attempts` classification from the live `ConnectorRegistry`, never from the `Plan`, retrying only idempotent failures up to the connector's own declared limit with exponential backoff.

### ExecutionEngine (`execution/engine.py`, Phases 5–6)

The orchestration host, mirroring `planning.engine.PlanningEngine`'s role exactly: `execute(plan, context) -> ExecutionResult`, implementing Intake, `StepScheduler` ordering, and the per-step loop (dependency check → cancellation check → confirmation gate → retrying connector call → bookkeeping) through to a best-effort completion — one step's failure never aborts an independent branch. Cancellation is checked once per step boundary, cooperative and never preemptive; a cancelled run's remaining steps are skipped in one pass and the run's final state becomes `CANCELLED` even if an earlier step had already failed. The optional post-`FAILED` rollback pass is attempted only if the caller opts in (a non-default `RollbackStrategy`), honestly recording `supported=False` for every connector shipped so far — never silently promoted to look like a success.

## Architecture Clarifications Resolved Mid-Implementation

Two genuine, previously-undetected gaps surfaced during implementation, each resolved by pausing, documenting the gap, and obtaining explicit clarification before proceeding — never silently decided:

- **`ExecutionRun.step_records` progress reporting** — implementation initially updated it once, in bulk, at the end of `execute()`; verifying against §20's own "may be read at any time, showing the current state of every step so far" surfaced the gap. Fixed to update incrementally, after every step.
- **`ExecutionEngine`'s access to a live `ConnectorRegistry`** (`ADR-0014`) — no approved contract gave `ExecutionEngine` a path to construct the `RetryPolicy` §17 requires. Resolved by having `ExecutionEngine` take a `RetryPolicy` as a required construction-time collaborator, mirroring `PlanningEngine`'s own run-vs-engine-level distinction (a swappable, construction-time collaborator) and `RegistryConnectorInvoker`'s own constructor-injection shape — not a Service Locator, not a new field on `ExecutionContext`, and not a new lookup mechanism of any kind.

## Architecture Validation

Phase 7's final validation exercised the complete, frozen Phase 1–6 implementation as one unit:

- **End-to-end flow** — a real `Goal → PlanningEngine → RuleBasedPlannerStrategy → Plan`, executed by `ExecutionEngine` against the real Filesystem connector, for a non-empty plan, an empty plan, and a plan whose capability had vanished from the live registry since planning time.
- **Architecture boundaries** — `execution/` has no direct or transitive import of `secrets_management/`, no direct import of `knowledge/` (a transitive `knowledge/` import via `planning.contract` is expected and accepted, mirroring `planning/`'s own identical relationship to `knowledge/`); `planning/` still has zero dependency on `execution/`, confirmed in both directions with the same AST-scan-plus-subprocess methodology Sprint 3/4 established.
- **Layer isolation** — `ExecutionEngine` never references `ConnectorRegistry` directly; a step not requiring confirmation, and a run that never reaches `FAILED`, never touch a forbidden `ConfirmationProvider`/`RollbackStrategy` double.
- **Contract stability** — a second, independently-written implementation of each of `ConfirmationProvider`, `RollbackStrategy`, and `ConnectorInvoker` all worked correctly against the same `ExecutionEngine`.
- **Scheduling** — the declared-order tie-break rule holds at the full-engine level (the actual order connector invocations happen in), not just inside `StepScheduler` in isolation.
- **Execution Philosophy & Ownership** — an independent branch's failure never aborts another; `ExecutionRun` is mutated only from `execution/engine.py`, verified by an AST scan of the entire project rather than a single example; `PlanNotExecutableError` is never raised for an ordinary capability-availability gap.

## Orchestration Determinism

A more precise claim than Planning's own, exactly as §24 states it: repeated runs of the same `(Plan, ExecutionContext)` against a fixed, scripted `ConnectorInvoker` always attempt the same steps, in the same order, with the same retry/gating decisions — verified directly by comparing step order, state, attempts, and confirmation outcome across repeated runs, fresh engine/context instances, and the empty-plan case. `ExecutionResult`'s *outcome* is deliberately not claimed to be byte-identical across runs, since `ExecutionRun`/`StepExecutionRecord` carry live wall-clock timestamps — the one place this Sprint's own state is not a pure function of its inputs, disclosed explicitly rather than overclaimed.

## Full Regression Validation

- **719/719 tests passing**
- **`mypy --strict` clean**
- **`ruff check` clean**
- **`ruff format` clean**

No bugs were found during Phase 7's validation. No production code changed as a result of it.

## Explicitly Out of Scope

Named here, not silently assumed solved: a real compensating/rollback action for any connector (the `RollbackStrategy` interface ships, with nothing yet to call), the confirmation-granting UX (`DenyAllConfirmationProvider` is a safe placeholder, not a product), the dependency-injection seam for connector credential access (`ADR-0009`'s C2, still unresolved — Filesystem needs no credential, so this Sprint's own reference execution path does not force it), distributed/multi-node execution, parallel execution of independent steps, event publication from `execution/` (contingent on a still-open `ExecutionContext.event_bus` clarification, orthogonal to `ADR-0014`), the Runtime module wrapper (`plugins/execution/`), and Configuration System integration. None of these were implemented in Sprint 5.
