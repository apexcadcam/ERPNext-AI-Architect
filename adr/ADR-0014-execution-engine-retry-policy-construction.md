# ADR-0014: `ExecutionEngine` Receives `RetryPolicy` at Construction, Not Through `ExecutionContext`

**Date:** 2026-07-24
**Status:** Accepted

## Context

`SPRINT5_ARCHITECTURE_PACKAGE.md §17` states that `RetryPolicy` re-resolves a step's `kind`/`idempotent` classification from the live `ConnectorRegistry` before deciding whether a failed invocation may be retried. Neither `ExecutionContext` (`§11`) nor `ExecutionEngine.execute(plan, context)`'s approved call signature (`§9.2`) provides any path to a `ConnectorRegistry` reference. This surfaced during Sprint 5 Phase 4 implementation (`execution/retry.py`): `RetryPolicy` was built to take a `ConnectorRegistry` directly in its own constructor — the minimal shape matching `§17`'s own text — but nothing in the approved architecture said how `ExecutionEngine` (Phase 5) would obtain one to construct a `RetryPolicy` from.

This is a genuine omission in the approved architecture, not a deferred implementation detail: `§17` makes an unconditional, specific claim about `RetryPolicy`'s behavior that the approved contracts have no mechanism to fulfill.

## Decision

`ExecutionEngine` takes a `RetryPolicy` instance as a required constructor parameter:

```
ExecutionEngine.__init__(self, retry_policy: RetryPolicy) -> None
```

assembled by the same composition root that constructs `RegistryConnectorInvoker(registry)` for `ExecutionContext.connector_invoker` (Sprint 5 Phase 3), from the same `ConnectorRegistry` instance. `execute(plan, context) -> ExecutionResult`'s own signature is unchanged.

Alternatives considered and rejected:

- **Add a `ConnectorRegistry`/`RetryPolicy` field to `ExecutionContext`.** Rejected: `ExecutionContext` (`§11`) is the Executor's per-call, per-run input bundle — its fields are documented as varying meaningfully from run to run. A `RetryPolicy` does not vary across runs for one `ExecutionEngine`'s lifetime; folding it into the per-call context would blur that distinction rather than respect it.
- **A Service Locator or ambient/global lookup.** Rejected: this project has never used implicit, ambient dependency resolution anywhere in its architecture; the Runtime's own Container is explicit and capability-resolved, reached only through a documented boot sequence Execution does not participate in (`§3` Non-Goals). An ad hoc lookup mechanism for this one dependency would be a materially larger, less consistent change than a constructor parameter.
- **A `RegistryProvider`/factory abstraction, injected instead of the registry itself.** Rejected as unnecessary indirection: nothing in this Sprint's scope requires the `ConnectorRegistry` to be swappable or lazily resolved — one instance exists for an `ExecutionEngine`'s entire lifetime, built once by its composition root.

## Consequences

- **Accepted:** a composition root must construct one `ConnectorRegistry` and use it to build both `RegistryConnectorInvoker(registry)` (for `ExecutionContext.connector_invoker`) and `RetryPolicy(registry)` (for `ExecutionEngine.__init__`). Neither `ConnectorRegistry`, `ConnectorInvoker`, `ExecutionContext`, nor `RetryPolicy`'s own already-approved shapes change.
- **General guideline, applied going forward:** a collaborator's dependency need is resolved through the layer — `ExecutionContext` versus an engine's own construction — whose lifetime actually matches that dependency's lifetime. Data that varies per call or per run belongs in the context passed to that call; a collaborator that is fixed for an engine's entire lifetime belongs in that engine's constructor. This distinction should be checked first whenever a future component's dependency need is discovered during implementation, before considering whether the context object itself needs a new field.
