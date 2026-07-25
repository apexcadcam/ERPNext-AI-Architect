# Sprint 7 Release Notes — Goal Orchestration

**Release:** `v0.8.0-goal-orchestration`
**Status:** Approved — all four phases passed architecture and implementation review; implementation frozen
**Branch:** `review/sprint7-goal-orchestration` → merged into `main`
**Depends on (frozen, unmodified):** Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer, Sprint 4 Planning Engine, Sprint 5 Execution Engine, Sprint 6 Runtime Integration (`v0.7.0-runtime-integration`), `ADR-0009`, `ADR-0014`

---

## Summary

Sprint 7 builds the component Sprint 6 named three times over and deliberately did not build: the caller that actually drives `Goal → PlanningEngine.create_plan() → ExecutionEngine.execute()`, resolving both `planning.engine` and `execution.engine` from the Container and assembling real `PlanningContext`/`ExecutionContext` instances. `GoalOrchestrator` composes two fully-built, independently-tested engines into a single, uniform call — no new planning logic, no new execution logic, only the composition that removes the duplicated wiring every future caller would otherwise need to reinvent. Every phase was implemented against the approved Sprint 7 Architecture Package and its three approved ADR candidates, with two forward-compatibility recommendations from architecture review incorporated before implementation began, and two further test recommendations incorporated before Phase 1 started. Sprint 7 modifies zero existing files — every phase added only new files, the lowest-risk profile of any Sprint in this project so far.

## What Shipped

### Orchestration Contracts (`orchestration/contract.py`, Phase 1)

`PlanningFailure` — a structured, immutable capture of a Planning-phase failure (`error_type`, `detail`), replacing an original bare-string proposal per architecture review's own forward-compatibility recommendation. `GoalRunResult` — the uniform, always-obtainable outcome of one `run_goal()` call, exactly one of two valid shapes: Planning failed (`plan`/`execution_result` both `None`, `planning_failure` populated) or Planning succeeded and Execution ran to whatever terminal state it reached (`plan`/`execution_result` both populated). No cross-field validator enforces this — pure data, matching `Plan`/`PlanStep`/`ExecutionRun`'s own established "the engine validates, the model doesn't" discipline.

### `GoalOrchestrator` (`orchestration/orchestrator.py`, Phase 2)

The pure orchestration class — constructible with zero Runtime involvement, mirroring `PlanningEngine`/`ExecutionEngine`'s own standalone shape. `__init__(planning_engine, execution_engine, connector_invoker)` takes the three collaborators fixed for its entire lifetime (ADR Candidate A, extending `ADR-0014`'s construction-time-vs-per-call test one level up the stack); `run_goal(goal, *, graph, confirmation_provider, runtime_context, correlation_id, available_capabilities=(), rollback_strategy=None, cancellation_token=None, event_bus=None) -> GoalRunResult` takes everything genuinely per-call. `PlannerStrategyError`/`PlanValidationError` are caught narrowly — never a bare `except Exception` — and captured as a `PlanningFailure`; any other exception, including `execution.errors.PlanNotExecutableError` (an engine-internal precondition violation, not a domain failure), is not caught and propagates unchanged (ADR Candidate B). Never mutates a `Goal`/`Plan`/`ExecutionResult` field, never reconstructs what either engine returns — proven by identity, not merely equality (architecture review's own added invariant 9).

### `OrchestrationModule` (`orchestration/module.py`, `plugins/orchestration/`, Phase 3)

Hosts a ready-to-use `GoalOrchestrator` as a Runtime Module, mirroring `ExecutionModule`'s exact shape one level up. Requires `integration.connector_registry`, `planning.engine`, and `execution.engine` — the first module in this project to depend on three capabilities across three different providing modules simultaneously. `init()` constructs a `RegistryConnectorInvoker(registry)` internally, mirroring `ExecutionModule`'s own already-approved pattern for the identical dependency, and hands it plus both resolved engines to a `GoalOrchestrator` it constructs and owns. Provides `orchestration.goal_runner`.

## Architecture Clarifications Resolved Before Implementation

Two review recommendations were incorporated into the approved architecture before any code was written:

- **`PlanningFailure` as a dedicated model, not a bare string** — a caller can now distinguish `PlannerStrategyError` from `PlanValidationError` programmatically via `error_type`, rather than parsing message text.
- **Invariant 9, added explicitly** — `GoalOrchestrator` owns orchestration and context assembly only; it must never perform planning logic, execution logic, or mutation of Planning or Execution domain objects. Verified by both a static AST check and a runtime identity proof.

Two further test recommendations were incorporated into the implementation plan before Phase 1 began: a dedicated spy test proving `ExecutionEngine.execute()` is never invoked when `PlanningEngine.create_plan()` fails, and a module-level identity test proving repeated resolution of `orchestration.goal_runner` returns the same `GoalOrchestrator` instance.

## Architecture Validation

Phase 4's final validation exercised the complete, frozen Phase 1–3 implementation as one unit:

- **End-to-end flow** — a real `Goal` through `container.resolve("orchestration.goal_runner").run_goal(...)` reaches both Planning and Execution for real, entirely through Container resolution; a `Goal` whose desired capability is unavailable produces an ordinary empty `Plan`, never an exception; a fully end-to-end run against the real, `PluginRegistry`-discovered Filesystem connector; confirmation that the orchestrator's own engines are the exact Container-resolved instances, not copies.
- **Architecture boundaries** — `orchestration/` has no forbidden import; `runtime/` still has no import of `orchestration/` anywhere, direct or transitive; `planning/`/`execution/` remain provably unaware `orchestration/` exists, confirmed at both the per-file (Phase 2) and whole-Sprint (Phase 4) level.
- **Dependency ordering** — a new, explicit three-precedes-one case proves `integration`, `planning`, and `execution` all precede `orchestration` in `PluginRegistry.dependency_order()`, not assumed to generalize from Sprint 6's own single/two-dependency tests.

## Full Regression Validation

- **836/836 tests passing**
- **`mypy --strict` clean**
- **`ruff check` clean**
- **`ruff format` clean**

No bugs were found in production code during Phase 4's validation. One self-caught authoring mistake — a stray placeholder assertion left over from drafting — was found and removed before it was ever committed to a reviewed phase.

## Migration Impact

None. Every file this Sprint touches is new; `planning/`, `execution/`, `integration/`, and `runtime/` remain byte-for-byte unmodified from `v0.7.0-runtime-integration`. `plugins/` gains one new, `enabled_by_default: true` entry, consistent with every other module.

## Explicitly Out of Scope

Named here, not silently assumed solved: `CapabilityResolver` (`available_capabilities` remains hand-supplied by whoever calls `run_goal()`); the `Agents` module named in `RUNTIME_ARCHITECTURE.md §4.7` (a full `Agent`/`Skill` composition host, a different, still-undesigned concept `GoalOrchestrator` was deliberately named to avoid colliding with); adaptive or iterative re-planning (`run_goal()` performs exactly one Plan-then-Execute pass — `RuleBasedPlannerStrategy` is purely deterministic, so a "failed, try again" loop would produce the identical `Plan` a second time); new orchestration-level event identifiers (`execution/events.py`'s own nine, threaded through `ExecutionContext.event_bus`, already let a subscriber reconstruct one Goal's full execution lifecycle); a CLI, API, or other real caller of `orchestration.goal_runner`; and `ADR-0009`'s C2 (the credential-injection seam, still unresolved). None of these were implemented in Sprint 7.
