# Sprint 8 Release Notes — Intelligence Abstraction Layer

**Release:** `v0.9.0-intelligence-abstraction`
**Status:** Approved — all five phases passed implementation review; implementation frozen
**Branch:** `review/sprint8-intelligence-abstraction` → merged into `main`
**Depends on (frozen, unmodified):** Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer, Sprint 4 Planning Engine, Sprint 5 Execution Engine, Sprint 6 Runtime Integration, Sprint 7 Goal Orchestration (`v0.8.0-goal-orchestration`)
**Architecture reference:** [Strategic Realignment v1–v4](STRATEGIC_REALIGNMENT.md) §9–§11 (v4); [Sprint 8 Implementation Plan](SPRINT8_IMPLEMENTATION_PLAN.md)

---

## Summary

Sprint 8 is the first sprint since the Strategic Realignment (v1–v4) and the first that is not part of the original Runtime build-out (Sprints 1, 3, 5–7). It delivers `intelligence/`: a paradigm-agnostic capability contract that separates *architectural knowledge* (owned by this project, the subject of Sprint 9 onward) from *reasoning* (an interchangeable, swappable implementation — an LLM today, potentially a constraint solver, a symbolic engine, or a technology that doesn't exist yet, tomorrow). Every method on `IntelligenceEngine` takes already-selected, structured evidence as input and returns a typed result — there is no method that accepts or returns a bare prompt string, which is what makes "the reasoning side must not invent knowledge" a property enforced by the type system, not a convention. Sprint 8 modifies **zero existing files** — all sixteen files across five phases are new, the same purely-additive profile Sprint 7 achieved. `runtime/`, `planning/`, `execution/`, `orchestration/`, `integration/`, and `knowledge/` remain byte-for-byte unmodified and, as of this release, have no awareness `intelligence/` exists at all — proven, not merely asserted (see Architecture Validation).

## What Shipped

### `IntelligenceEngine` Contracts (`intelligence/contract.py`, Phase 1)

Nine frozen, `extra="forbid"` data models (`EvidenceItem`, `Requirement`, `RequirementUnderstanding`, `Candidate`, `TradeoffAssessment`, `ProposedArchitecture`, `ArchitectureCritique`, `ChallengedAssumption`, `AssumptionChallenge`) and the `IntelligenceEngine` ABC itself, exposing exactly four methods (`interpret_requirement`, `evaluate_tradeoff`, `critique_architecture`, `challenge_assumptions`) — the fifth application of this project's established "one fixed contract, many swappable backends" pattern (`SecretsBackend`, `GraphStoreAdapter`, `ConnectorLifecycle`, `PlannerStrategy`, now `IntelligenceEngine`). `EvidenceItem` is deliberately a generic primitive this package owns outright — a disclosed, implementation-driven correction of the Strategic Realignment's own prose, which had sketched it carrying a `KnowledgeLayer` field that doesn't exist in code until Sprint 9, and which would have coupled domain-agnostic infrastructure to an ERP-specific concept regardless of sequencing.

### `NullIntelligenceEngine` / `ValidatingIntelligenceEngine` / `CitationError` (Phase 2)

`NullIntelligenceEngine` — the deterministic reference implementation, chosen first for the same reason `RuleBasedPlannerStrategy` was: lowest risk, no external dependency, proves the contract end to end. Ranks candidates by summed evidence weight, ties broken by `candidate_id`; returns an empty critique/assumption-challenge unconditionally rather than fabricating either. `ValidatingIntelligenceEngine` — the one, non-bypassable enforcement point: wraps any `IntelligenceEngine`, passes a conforming response through completely unmodified, and raises `CitationError` immediately (never logged-and-continued, never repaired) the moment a response cites an evidence or candidate id absent from the exact call it was given.

### `IntelligenceModule` (Phase 3)

The Runtime-facing host, registering exactly one capability, `intelligence.engine`. Reuses every existing mechanism without exception: `Module`/`Container` (unchanged), the `"runtime.config"` config-driven-resolution pattern `IntegrationModule` established in Sprint 6 (`connector_search_paths` there, `intelligence_engine` here), and the Container's own SINGLETON caching for repeated-resolution identity. Unknown or absent configuration falls back to `"null"`; every configuration outcome — known, unknown, or absent — resolves to a `ValidatingIntelligenceEngine`-wrapped engine. No unwrapped engine can ever be obtained from the Runtime.

### `AnthropicAdapter` (Phase 4)

The one adapter this sprint ships, existence proof that `IntelligenceEngine` can be satisfied by a real provider. `AnthropicClientProtocol` is this project's own narrow, structural seam (mirroring `GraphReader`'s/`ConnectorInvoker`'s established "a Protocol needs no vendor import to define" pattern) — a disclosed design choice: neither the protocol nor the adapter imports the `anthropic` package at all, since dependency injection means the adapter never constructs a client, so nothing here needs the concrete SDK type to type-check against. Translation only: serializes typed input to JSON, calls the injected client, and converts the raw text response back to a typed contract via `Pydantic.model_validate` — reusing Pydantic's own validation rather than hand-rolled field checks — raising `MalformedResponseError` on invalid JSON or a schema mismatch. No ranking, no citation logic, no retry, no caching.

### Architecture Boundary Tests (`tests/sprint8/test_architecture_boundaries.py`, Phase 5)

Converts every one of Sprint 8's architectural rules into an executable, whole-sprint test, on the identical AST-scan-plus-subprocess methodology `tests/sprint3/` through `tests/sprint7/` already established: no existing package imports `intelligence/` yet (direct and transitive); only `intelligence/adapters/` may import a vendor SDK or a networking library; `intelligence/` imports no other domain package (direct and transitive, across all three real entry points); and the Container remains the only runtime integration mechanism — verified by an exact one-`register()`-call-site count, the absence of any second registry/locator-shaped class anywhere in the package, and an end-to-end proof that the registered capability resolves through the real `Container`.

## Architecture Decisions Made During Implementation

Two small, disclosed corrections surfaced by implementation, neither requiring architecture review under the Freeze's own exceptions (implementation impossible as literally sketched / avoids unnecessary coupling):

- **`EvidenceItem` is `intelligence/`'s own generic type**, not the `SupportingEvidence` (with a `KnowledgeLayer` field) the Strategic Realignment's prose sketched — `analysis/` (Sprint 12) will translate its richer evidence down to this shape when it exists.
- **`AnthropicAdapter` imports no vendor SDK at all** — the Protocol-based seam makes this possible without weakening "only `adapters/` may import one," which remains true and enforced for whenever a real, network-calling implementation is eventually added.

## Architecture Validation

- **Isolation, both directions** — `runtime/`, `planning/`, `execution/`, `orchestration/`, `integration/`, `knowledge/` have no direct import of `intelligence/`, confirmed by AST scan across all six, plus transitive `sys.modules` checks after importing `runtime.boot`, `orchestration`, and `knowledge`. `intelligence/` has no direct import of any of `knowledge`/`analysis`/`planning`/`execution`/`orchestration`, confirmed directly and transitively across all three of its own real entry points (`intelligence`, `intelligence.module`, `intelligence.adapters.anthropic_adapter`).
- **Vendor and network isolation** — only `intelligence/adapters/` may import `{anthropic, openai, google, langchain, litellm}` or `{httpx, requests, urllib, aiohttp}`; verified absent everywhere else in the package.
- **No alternative registration mechanism** — exactly one `container.register(...)` call site exists in the whole package (`intelligence/module.py`); no class named with a `registry`/`container`/`locator` fragment exists anywhere in `intelligence/`; the registered capability is proven, end to end, to resolve through the real `runtime.container.di.Container`.
- **No production code bypasses `ValidatingIntelligenceEngine`** — `IntelligenceModule.init()` never registers an unwrapped engine under any configuration outcome (default, explicit, unknown, or absent), tested across all four.

## Full Regression Validation

- **970/970 tests passing** (Sprint 8 itself contributes 134: 47 contract, 16 `NullIntelligenceEngine`, 15 `ValidatingIntelligenceEngine`, 17 module, 25 adapter, 14 sprint-level boundary)
- **100% line and branch coverage**, `intelligence/` package-wide (190/190 statements, 8/8 branches)
- **`mypy --strict` clean** across every file this Sprint added
- **`ruff check` clean**; **`ruff format` clean** for every file this Sprint added

Pre-existing, unrelated gaps confirmed unchanged from every prior Sprint's own release notes: the same 15 `mypy --strict` findings in `tests/test_pipeline_engine.py`/`tests/test_event_bus.py`, and a `ruff format` drift in nine pre-existing Sprint-1 files (`runtime/cli.py`, `runtime/config/loader.py`, `runtime/events/bus.py`, `runtime/pipeline/engine.py`, `runtime/registry/plugin_registry.py`, and four of their own tests) — confirmed via `git diff main` to carry zero changes from this Sprint, present on `main` before this branch existed.

## Migration Impact

None. Every file this Sprint touches is new; `runtime/`, `planning/`, `execution/`, `orchestration/`, `integration/`, and `knowledge/` remain byte-for-byte unmodified from `v0.8.0-goal-orchestration`. **Unlike every prior domain module, `plugins/` gains no new entry in this release** — `intelligence/module.py` is a complete, tested `Module` implementation, but wiring it into the real `PluginRegistry`-discovered `plugins/` directory was explicitly out of this Sprint's scope (see Explicitly Out of Scope) and is deferred to whichever future sprint first needs `intelligence.engine` resolvable through a real Runtime boot.

## Explicitly Out of Scope

Named here, not silently assumed solved: a `plugins/intelligence/` entry (the module exists but is not yet Runtime-discoverable); any provider beyond `AnthropicAdapter` (OpenAI, Gemini, a local model); the `architectural_intelligence` `PipelineDefinition` composing `IntelligenceEngine` into the multi-stage Evidence Selection → Core Intelligence → Self-Critique → Challenge Assumptions → Risk Analysis → Decision Validation sequence (Strategic Realignment v4 §11 — reuses the existing `runtime.pipeline.PipelineEngine`, not built here); the `analysis/` package and its `Requirement`/`Recommendation`/`ERPAnalysisReport` types; `knowledge/erpnext/` and any Layer 1–4 content; and Reasoning History / the ADR feedback loop (v4 §13). None of these were implemented in Sprint 8.
