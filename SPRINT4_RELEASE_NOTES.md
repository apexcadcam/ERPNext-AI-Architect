# Sprint 4 Release Notes — Planning Engine

**Release:** `v0.5.0-planning-engine`
**Status:** Approved — all six phases passed architecture review; implementation frozen
**Branch:** `review/sprint4-planning-engine` → merged into `main`
**Depends on (frozen, unmodified):** Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer & Knowledge Graph (`v0.4.0-integration-layer`)

---

## Summary

Sprint 4 delivers the Planning Engine: given a `Goal` and a read-only view of the Knowledge Graph plus a snapshot of available capabilities, it produces an executable `Plan` — and nothing more. Execution, connector invocation, capability resolution, LLM reasoning, and Runtime/Configuration wiring are all explicitly out of scope, named throughout the architecture package rather than silently assumed solved. Every phase was implemented against the approved Sprint 4 Architecture Package with no redesign, and the final validation phase (Phase 6) confirmed the whole package holds together as one coherent unit with zero bugs found and zero production changes required.

## What Shipped

### Planning Contracts (`planning/contract.py`, Phase 1)

The foundational, frozen data models every other component builds on: `Goal` (what a caller wants planned), `RuntimeContextInfo` (environment/correlation metadata only — never a credential), `CapabilityDescriptor` (a capability's shape as plain data, echoing `integration.contract.ConnectorOperation`'s vocabulary without importing it), `Plan` (the Planner's sole, inert output), and `PlanStep` (one node in a `Plan`'s dependency DAG). All immutable, fully typed, and — with the single disclosed exception of `PlanStep`/non-empty `Plan` (whose opaque `parameters: dict[str, Any]` field makes them unhashable, mirroring `runtime.events.bus.Event.payload`'s identical precedent) — hashable and equality-comparable.

### PlanningContext (`planning/context.py`, Phase 2)

The Planner's complete, read-only input bundle: exactly four fields — `graph`, `available_capabilities`, `runtime_context`, `correlation_id` — frozen, with no methods and no cross-field validation. Assembled entirely outside `planning/`'s own package boundary; nothing in this Sprint constructs one itself.

### GraphReader Abstraction (`planning/graph_reader.py`, Phase 2)

A structural `typing.Protocol` exposing exactly the seven read-only methods of `knowledge.graph.GraphStoreAdapter` (`get_node`, `get_node_by_artifact_id`, `outgoing_edges`, `incoming_edges`, `neighbors`, `traverse`, `all_nodes`) — no `create_node`/`create_edge`. Copied verbatim from the real Adapter's own signatures so it cannot silently drift out of sync. No wrapper or adapter class exists anywhere: any real `GraphStoreAdapter` (e.g. `InMemoryGraphStore`) already satisfies `GraphReader` purely structurally. This is what makes "the Planner never performs graph writes" a structural guarantee rather than a documented convention.

### Plan Validation (`planning/validation.py`, Phase 3)

`validate_plan(plan, context, *, raise_on_failure=True) -> PlanValidationReport` — the single, uniform gate every candidate `Plan` passes through, mirroring `integration.registry.ConnectorRegistry.validate()`'s exact two-mode shape. Five rules, all violations collected together rather than failing fast: every step's capability must be available; every `depends_on` reference must target a real step; no dependency cycle (DFS-based, deterministic); an empty plan is valid by construction; and a step may never *understate* the `requires_confirmation` its capability's descriptor demands.

### PlanningEngine (`planning/engine.py`, Phase 4)

The pure orchestration host: accepts a `Goal` + `PlanningContext`, resolves the configured strategy, invokes it, invokes `validate_plan` unmodified, and returns the validated `Plan`. No planning, graph, capability, or validation logic of its own. A raising or misbehaving strategy is wrapped as `PlannerStrategyError`; an invalid candidate plan propagates `PlanValidationError` unwrapped.

### PlannerStrategy (`planning/strategy.py`, Phase 5)

The permanent, swappable reasoning-core contract — an `ABC` with a single abstract `create_plan(goal, context) -> Plan` method, replacing Phase 4's temporary `Callable` placeholder. The fourth application of this project's own "one contract, many backends, chosen by configuration" pattern, after `SecretsBackend`, `GraphStoreAdapter`, and `ConnectorLifecycle`.

### RuleBasedPlannerStrategy (`planning/strategy.py`, Phase 5)

The one, minimal, deterministic reference implementation named in the architecture package's own Migration Strategy — chosen first for the same reason the Filesystem Connector was chosen first among connectors in Sprint 3: lowest risk, no external dependency, proves the framework end to end. For every capability a `Goal` desires that is also available, it emits exactly one dependency-free `PlanStep`, in the goal's own order, with `requires_confirmation` copied directly from the matching `CapabilityDescriptor`. It is deliberately not intelligent: no graph search, no AI, no ERPNext awareness, no heuristics, no optimization — and, verified by a `GraphReader` double whose every method raises if called, it never touches the Knowledge Graph at all.

## Architecture Validation

Phase 6's final validation exercised the complete, frozen Phase 1–5 implementation as one unit:

- **End-to-end flow** — `Goal → PlanningEngine → PlannerStrategy → validate_plan → Plan`, verified for both non-empty and empty plans.
- **Strategy independence** — a second, deliberately differently-behaved `PlannerStrategy` (defined only in tests, never shipped in `planning/`) proved `PlanningEngine` depends on the contract alone, not on `RuleBasedPlannerStrategy`'s own decisions.
- **Architecture boundaries** — AST-scan plus subprocess `sys.modules` checks (reusing Sprint 3 Phase 6's exact methodology) confirmed zero direct or transitive import of `integration/` or `secrets_management/` anywhere in `planning/`.
- **Layer isolation** — `PlanningEngine` never accesses `GraphReader`; `RuleBasedPlannerStrategy` never calls `validate_plan`; `validate_plan` never touches the graph; `Goal`/`PlanningContext`/`Plan` are never mutated. Each claim verified twice: a precise AST check (immune to docstring false positives) and a runtime check (a `ForbiddenGraph` double that raises on any access).
- **Contract stability** — three independent `PlannerStrategy` implementations all worked correctly against the same `PlanningEngine`, including hot-swapping via `register_strategy(..., override=True)`.

## Deterministic Planning

Every layer of Sprint 4 was built and tested to be a pure function of its inputs. `validate_plan` iterates only fixed-order tuples, never a set. `RuleBasedPlannerStrategy` uses a fixed, disclosed `created_at` placeholder and deterministically-derived `plan_id`/`step_id` values rather than a wall-clock timestamp, specifically so repeated calls with identical `(Goal, PlanningContext, PlannerStrategy)` produce **byte-equivalent** `Plan`s — verified directly via `model_dump_json()` equality across repeated runs, fresh engine/strategy instances, and the empty-plan case.

## Full Regression Validation

- **530/530 tests passing**
- **`mypy --strict` clean**
- **`ruff check` clean**
- **`ruff format` clean**

No bugs were found during Phase 6's validation. No production code changed as a result of it.

## Explicitly Out of Scope

Named here, not silently assumed solved: `CapabilityResolver`, Configuration System integration, the Runtime module wrapper (`plugins/planning/`), the Execution Engine, connector invocation, graph search algorithms, LLM-based planning, and ERPNext-specific planning logic. None of these were implemented in Sprint 4.
