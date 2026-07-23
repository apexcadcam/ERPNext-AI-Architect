# SPRINT 2 IMPLEMENTATION PLAN — Knowledge Factory

**Branch:** `review/sprint2-knowledge-factory`
**Base:** `main` @ `v0.1.0-runtime-bootstrap` (commit `a251cb1`)
**Status:** Planning only. No implementation, no stubs, no placeholder code has been written against this plan.

---

## 1. Sprint Objective

Implement the **Knowledge Factory** — the term this branch's name refers to, defined precisely and only once in the frozen architecture, in [`docs/studio/STUDIO_EVENT_MODEL.md` § 2](docs/studio/STUDIO_EVENT_MODEL.md), under "Knowledge Factory Status":

> *"Studio-level grouping term for Extraction → Pattern Extraction → Conflict Resolution → Validation — no new Runtime module."*

Concretely, Sprint 2 builds the first two domain modules (Extractor, Validator) on top of Sprint 1's Runtime — the first Sprint to plug a real capability into the Module/Plugin/DI/Pipeline/Event contracts Sprint 1 built but left empty — plus the artifact schemas and conflict-resolution logic those two modules require to do real work. It does **not** build a Crawler, a Knowledge Graph store, embeddings, retrieval, or any Studio-facing UI; those are named explicitly in [§3](#3-out-of-scope-items).

"No new Runtime module" (the Studio doc's own qualifier) is read literally: Sprint 2 adds domain modules and Pipeline Definitions *using* Sprint 1's existing `Module`, `Container`, `PluginRegistry`, `PipelineEngine`, and `EventBus` primitives, unmodified. No change to `runtime/` itself is in scope unless [§8](#8-risks) identifies a genuine defect Sprint 1 left behind — and even then, only a fix, never a redesign.

---

## 2. Scope

Per [`docs/runtime/PIPELINE_ENGINE.md § 4`](docs/runtime/PIPELINE_ENGINE.md), two named Pipeline Definitions are in scope, registered against Sprint 1's `PipelineEngine` and executed against **synthetic/fixture input only** (no live source — see [§9](#9-dependencies)):

- **`knowledge.validation`** — the eight fixed-order gates from [`KNOWLEDGE_VALIDATION_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md): Schema Validation → Duplicate Detection → Version Conflict Detection → Source Verification → Trust Verification → Engineering Review → Human Approval Gate → Confidence Scoring.
- **`knowledge.graph_build`**, *minus its final stage* — Extraction and Pattern Extraction from [`KNOWLEDGE_EXTRACTION_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md), and Conflict Resolution from [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md). The fourth stage in that Pipeline Definition's frozen stage list — **Graph Node/Edge Materialization** — is explicitly excluded; see [§3](#3-out-of-scope-items) and [§8](#8-risks) for why splitting a single named Pipeline Definition across two Sprints is called out as a risk rather than done silently.

In scope, supporting the two Pipeline Definitions above:

- **Artifact envelope and type schemas** from [`KNOWLEDGE_ARTIFACTS.md`](docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md) — the common envelope, plus `Knowledge Document`, `Knowledge API`, `Pattern`/`Anti-Pattern`, `Best Practice`, `Example`, `Workflow`, and `Knowledge Conflict`. These have never been implemented as code before this Sprint; Sprint 1 built Runtime scaffolding only, with no domain schemas.
- **Two domain modules** — `Extractor` and `Validator` — each a `runtime.modules.base.Module` subclass with its own `module.yaml` manifest, following exactly the same plugin shape Sprint 1's test fixtures already exercise (`tests/conftest.py`'s `make_plugin`), now with real (not test-only) behavior.
- **Conflict resolution logic** implementing [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md)'s 9-level precedence hierarchy, the 5 named scenarios, and the non-negotiable "Undecided — surface to a human" fallback — invoked both from `knowledge.validation`'s Version Conflict Detection gate and from `knowledge.graph_build`'s Conflict Resolution stage (the two call sites the frozen spec itself names).

---

## 3. Out-of-Scope Items

Explicitly **not** built in Sprint 2, each for a specific, stated reason:

| Item | Reason |
|---|---|
| A real Crawler / any live source acquisition | No Sprint has built the Crawler yet (`docs/crawler/` remains architecture-only); `knowledge.formation` (Acquisition → Cleaning → Normalization → Deduplication, per [`KNOWLEDGE_PIPELINE.md`](docs/knowledge-pipeline/KNOWLEDGE_PIPELINE.md)) is not in this Sprint's Pipeline Definition list. |
| Graph Node/Edge Materialization, and the Knowledge Graph module itself | [`KNOWLEDGE_GRAPH_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md) is "architecture only, not implemented" and describes a property-graph storage/traversal layer outside a bootstrap Sprint's reach; also outside the Studio's own "Knowledge Factory" term, which stops at Validation. |
| Embeddings and Retrieval | `knowledge.retrieval_index` ([`EMBEDDING_STRATEGY.md`](docs/knowledge-pipeline/EMBEDDING_STRATEGY.md), [`RETRIEVAL_STRATEGY.md`](docs/knowledge-pipeline/RETRIEVAL_STRATEGY.md)) explicitly consumes validated Knowledge Graph nodes, which do not exist without the Graph module above. |
| Engineering Rule lifecycle changes | [`KNOWLEDGE_ACQUISITION_ARCHITECTURE.md § 4`](docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) is explicit: no pipeline stage may set `Status: Stable` on an `Engineering Rule`; a rule-shaped candidate stops at `Draft` and the existing, unchanged [Research → Engineering Rule lifecycle](docs/ENGINEERING_RULE_SPECIFICATION.md#7-future-rules--mandatory-lifecycle) owns everything past that. Sprint 2 only produces `Draft` candidates, never advances them. |
| Any Studio UI or event-visualization surface | [`STUDIO_ARCHITECTURE.md`](docs/studio/STUDIO_ARCHITECTURE.md) is a separate, passive-observer architecture; nothing in it is implementation work for this Sprint. Sprint 2's modules publish the events [`STUDIO_EVENT_MODEL.md`](docs/studio/STUDIO_EVENT_MODEL.md)'s "Knowledge Factory Status" table already names (`ArtifactCreated`, `ConflictDetected`, `ValidationCompleted`, `HumanApprovalRequested`/`HumanApprovalResolved`) — a future Studio Sprint subscribes to them, unmodified. |
| Human Approval Gate's actual human-facing workflow (queueing UI, notification, approval action) | [`KNOWLEDGE_VALIDATION_SPEC.md § 7`](docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#7-human-approval-gate) defines *when* a human is required, not a review tool. Sprint 2 implements the gate as a stage that halts a pipeline run at `pending-human-approval` and exposes a programmatic decision entrypoint (see [§5](#5-public-apis)); building an actual review UI is out of scope. |
| Runtime/Container/Registry/EventBus/PipelineEngine changes | Sprint 1 delivered these as a stable, reviewed, tagged API surface (`v0.1.0-runtime-bootstrap`). Sprint 2 consumes them as-is; any change would be a Sprint 1 API break, not Sprint 2 scope. |
| Any real, network-backed Trust Score or Source Verification lookup | [`KNOWLEDGE_VALIDATION_SPEC.md § 4`](docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#4-source-verification) re-fetches live source content; [§5](docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#5-trust-verification) reads `KNOWLEDGE_SOURCE_CATALOG.md`'s live Trust Score. Without a Crawler, Sprint 2 implements both stages' *logic* against fixture-supplied source metadata (a stand-in `Knowledge Source` record and a stand-in "re-fetch" function), not a real HTTP re-verification. |

---

## 4. Components to Implement

1. **`knowledge/artifacts` — artifact schema package.** Pydantic models for the common envelope ([`KNOWLEDGE_ARTIFACTS.md § 1`](docs/knowledge-pipeline/KNOWLEDGE_ARTIFACTS.md#1-the-common-envelope)) and each in-scope artifact type (`KnowledgeDocument`, `KnowledgeAPI`, `Pattern`, `AntiPattern`, `BestPractice`, `Example`, `Workflow`, `KnowledgeConflict`). No persistence layer — in-memory dataclass/Pydantic objects only, consistent with Sprint 1 having no storage layer either.
2. **`knowledge/extraction` — the Extractor module.** One `Module` subclass (`ExtractorModule`) implementing extraction rules for a first, deliberately small subset of [`KNOWLEDGE_EXTRACTION_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_EXTRACTION_SPEC.md)'s per-source-type rules (see [§8](#8-risks) for why "all ten source types" is not attempted in one Sprint), plus the Pattern Extraction second pass ("recurring shape across ≥2 artifacts").
3. **`knowledge/validation` — the Validator module.** One `Module` subclass (`ValidatorModule`) implementing all eight gates as `StageCallable`s bound to `knowledge.validation`'s stage capabilities.
4. **`knowledge/conflict` — conflict resolution logic.** A pure-logic component (not itself a `Module` — it is invoked *by* the Validator's Version Conflict Detection stage and by the graph_build Pipeline's Conflict Resolution stage, per [§2](#2-scope)) implementing [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md)'s precedence hierarchy.
5. **Pipeline Definition registration.** `PipelineDefinition`/`StageDefinition` instances for `knowledge.validation` (8 stages) and the in-scope `knowledge.graph_build` stages (Extraction, Pattern Extraction, Conflict Resolution), registered with a `PipelineEngine` the same way `tests/` already constructs one, per Sprint 1's existing `PipelineEngine.register()` contract.
6. **Module manifests.** `module.yaml` for `extractor` and `validator`, declaring `capabilities_provided` (the stage capabilities each binds to), `capabilities_required` (nothing cross-module in Sprint 2 — see [§6](#6-internal-architecture)), `pipeline_stage_bindings`, and `events_published` per [`STUDIO_EVENT_MODEL.md`](docs/studio/STUDIO_EVENT_MODEL.md)'s Knowledge Factory Status table.

---

## 5. Public APIs

Following Sprint 1's own convention: modules expose behavior only through capabilities resolved via the `Container`, never through direct imports of another module's internals ([`DEPENDENCY_INJECTION.md § 1`](docs/runtime/DEPENDENCY_INJECTION.md)).

**Capabilities provided:**

| Capability | Provided by | Shape |
|---|---|---|
| `knowledge.extract` | Extractor | `(KnowledgeDocument, PipelineContext) -> (list[Artifact], StageOutcome)` — the Extraction stage callable. |
| `knowledge.extract_patterns` | Extractor | `(list[Artifact], PipelineContext) -> (list[Artifact], StageOutcome)` — the Pattern Extraction stage callable. |
| `knowledge.validate.schema` … `knowledge.validate.confidence_score` | Validator | Eight capabilities, one per gate, each `(Artifact, PipelineContext) -> (Artifact, StageOutcome)` — matching `PIPELINE_ENGINE.md § 2`'s stage execution contract exactly, so each gate is independently a `StageDefinition.capability`. |
| `knowledge.resolve_conflict` | Conflict Resolution | `(ConflictCase, PipelineContext) -> (ConflictResolution, StageOutcome)` — `ConflictResolution` is either a decided outcome or `Undecided`, never silently defaulted (per [`KNOWLEDGE_CONFLICT_RESOLUTION.md`](docs/knowledge-pipeline/KNOWLEDGE_CONFLICT_RESOLUTION.md)'s non-negotiable fallback). |
| `knowledge.approval.resolve` | Validator | `(approval_id: str, decision: ApprovalDecision) -> None` — the programmatic entrypoint a future human-facing tool (or, in Sprint 2's own tests, a fixture) calls to resolve a pending Human Approval Gate; not a UI, per [§3](#3-out-of-scope-items). |

**Events published**, per [`STUDIO_EVENT_MODEL.md`](docs/studio/STUDIO_EVENT_MODEL.md)'s existing catalog (no new event names invented — Sprint 2 populates events the Studio doc already specifies as belonging to Extractor/Validator): `ArtifactCreated`, `ConflictDetected`, `ValidationCompleted`, `HumanApprovalRequested`, `HumanApprovalResolved`.

No capability in this Sprint requires anything from another *module* — `capabilities_required` on both manifests is empty, because Extraction and Validation each depend only on the `PipelineEngine`/`Container` primitives Sprint 1 already provides directly, not on each other. Sequencing between them is expressed as Pipeline Definition stage order, not as a cross-module capability dependency — see [§6](#6-internal-architecture).

---

## 6. Internal Architecture

```
                         PipelineEngine (Sprint 1, unmodified)
                                    │
                ┌───────────────────┴────────────────────┐
                │                                          │
   PipelineDefinition("knowledge.graph_build")   PipelineDefinition("knowledge.validation")
   stages: Extraction, Pattern Extraction,        stages: Schema, Duplicate, VersionConflict,
           Conflict Resolution                             SourceVerify, TrustVerify,
                │            │                              EngineeringReview, HumanApproval,
                │            │                              ConfidenceScoring
     knowledge.extract  knowledge.extract_patterns                  │
                │            │                          knowledge.validate.* (x8)
                ▼            ▼                                      │
         ExtractorModule (init/start/stop/health_check)      ValidatorModule (same)
                │                                                    │
                └──────────────► knowledge.resolve_conflict ◄────────┘
                                  (Conflict Resolution logic,
                                   invoked from both pipelines'
                                   conflict-detecting stages)
```

- **`ExtractorModule`** and **`ValidatorModule`** each implement Sprint 1's `Module` ABC (`runtime/modules/base.py`): `init(container)` registers their stage capabilities into the `Container` (`CapabilityScope.SINGLETON` — stateless, pure-function stage logic, no per-run state held on the module itself); `start()`/`stop()` are no-ops (no ongoing behavior beyond stage invocation, same as Sprint 1's own `_TestModule` fixture shape); `health_check()` reports `healthy=True` unconditionally in Sprint 2 (nothing external to check yet — no live source, no real storage).
- **Conflict resolution is a plain library, not a `Module`.** It has no lifecycle, no manifest, and is called directly by both `ValidatorModule`'s Version Conflict Detection stage and `ExtractorModule`-adjacent Conflict Resolution stage — both modules import it directly (an internal, same-Sprint dependency, not a cross-module capability), because it is shared logic within the Knowledge Factory grouping, not a separate domain module per [`MODULE_SYSTEM.md`](docs/runtime/MODULE_SYSTEM.md)'s "modules — Crawler, Parser, Extractor, Validator, ..." enumeration (Conflict Resolution is not named as its own module there).
- **Stage callables are pure functions of `(input, PipelineContext) -> (output, StageOutcome)`**, per `PIPELINE_ENGINE.md § 2` and Sprint 1's own `StageCallable` type alias in `runtime/pipeline/engine.py` — every gate and extraction step in this Sprint is written to that exact shape, so `PipelineEngine._execute_stage`'s retry/rollback machinery (already implemented and tested in Sprint 1) applies to Sprint 2's stages with zero changes to the Engine.
- **Human Approval Gate as a pipeline pause, not a blocking call.** Per `KNOWLEDGE_VALIDATION_SPEC.md § 7`, most artifacts skip it; when required, the `knowledge.validate.human_approval` stage returns `StageOutcome.RETRY_REQUESTED`-adjacent semantics is *not* used — instead it persists a `PendingApproval` record (in-memory dict for Sprint 2, per [§3](#3-out-of-scope-items)'s no-persistence-layer note) and returns `StageOutcome.FAILURE` with a distinguishable reason, halting that pipeline run; `knowledge.approval.resolve()` is the separate, explicit re-entry point a caller uses once a decision is made, starting a *new* pipeline run continuing from Confidence Scoring rather than resuming the halted run in place — this asymmetry (halt now, explicit restart later, not an in-place resume) is called out as a design decision in [§8](#8-risks) since `PIPELINE_ENGINE.md` does not itself specify a resume primitive.

---

## 7. Execution Order

1. **Artifact schemas first** (`knowledge/artifacts`) — every stage callable's signature depends on these types existing; nothing else can be written or tested first.
2. **Conflict resolution logic** (`knowledge/conflict`) — implemented and unit-tested standalone (pure functions over fixture `ConflictCase`s), since both the Extractor's and Validator's pipelines call into it and it has no dependency on either.
3. **Validator module and the eight `knowledge.validate.*` stage callables** — built and tested next, ahead of the Extractor, because Extraction's own output (an `Artifact`) is exactly what Validation consumes, so having Validation's contract fixed first lets Extraction be written directly against a known consumer shape rather than guessing it.
4. **Extractor module** (Extraction, then Pattern Extraction) — built against the now-fixed `Artifact` schemas and Validator contract.
5. **Pipeline Definition registration and wiring** — `knowledge.validation` and the in-scope `knowledge.graph_build` stages assembled into `PipelineDefinition`s and registered with a `PipelineEngine`, exercised end-to-end with fixture `KnowledgeDocument` input.
6. **`module.yaml` manifests for both modules** — written last, once both modules' actual `capabilities_provided`/`events_published` are final, so the manifest is a true declaration of finished behavior rather than a guess written before the code (mirroring Sprint 1's own manifest-after-behavior discipline, visible in how `tests/conftest.py`'s `make_plugin` factory builds manifests from already-known capability lists).
7. **CLI surfacing** (if any — see [§8](#8-risks)) and end-of-Sprint checklist (pytest, mypy, ruff, Sprint report, single commit), unchanged from the process this project has followed since Sprint 1.

---

## 8. Risks

- **Splitting `knowledge.graph_build` across Sprints is a Pipeline Definition boundary this Sprint invents, not one the frozen architecture names.** `PIPELINE_ENGINE.md § 4` defines `knowledge.graph_build` as one Pipeline Definition with four stages (Extraction, Pattern Extraction, Conflict Resolution, Graph Node/Edge Materialization). Sprint 2 registers only the first three stages under that name, deferring the fourth to whichever future Sprint builds the Knowledge Graph module. This is the smallest deviation available (three of four stages, in the frozen order, under the frozen name) but is still a deviation from "register the Pipeline Definition as specified" — flagged here rather than done silently, per this project's standing practice of documenting rather than resolving architectural tensions unilaterally.
- **A genuine ordering inconsistency exists between frozen documents regarding Validation vs. Extraction.** `KNOWLEDGE_ACQUISITION_ARCHITECTURE.md § 2`'s pipeline diagram and `PIPELINE_ENGINE.md § 4`'s Pipeline Definition table both place `knowledge.validation` *before* extraction/`knowledge.graph_build`. But `KNOWLEDGE_VALIDATION_SPEC.md`'s own Authority line states it "Gates every artifact produced by `KNOWLEDGE_EXTRACTION_SPEC.md`" — i.e., artifacts that exist only *after* Extraction runs — and its Trust Verification table ([§5](docs/knowledge-pipeline/KNOWLEDGE_VALIDATION_SPEC.md#5-trust-verification)) is keyed by artifact `type` (`Knowledge API`, `Pattern`, ...), types that are assigned by Extraction, not by raw `Knowledge Document`s. `STUDIO_EVENT_MODEL.md`'s own "Knowledge Factory" term lists the order as *Extraction → Pattern Extraction → Conflict Resolution → Validation*, agreeing with `KNOWLEDGE_VALIDATION_SPEC.md`'s Authority line, not with the two diagram/table documents. **This plan follows Validation-after-Extraction** (the Studio term's explicit order, and the Validation spec's own stated scope), because a document specifically scoped to defining validation's input is treated as more authoritative on that question than an entry-point summary diagram — but this is exactly the kind of frozen-architecture inconsistency this project's standing rule requires surfacing rather than silently picking a side on. Recommend a human confirms this reading before Sprint 2 implementation begins.
- **No real Crawler means Extraction/Validation can only be exercised against synthetic fixtures.** Same pattern Sprint 1 already used (`tests/conftest.py`'s `make_plugin` stands in for a real plugin); Sprint 2's tests will use hand-authored fixture `Knowledge Document`s and a stand-in `Knowledge Source` catalog entry rather than any live content. This means Sprint 2 validates the *pipeline mechanics* (stage sequencing, gate logic, conflict precedence) genuinely, but cannot validate real extraction-rule accuracy against real ERPNext documentation — that only becomes possible once a Crawler Sprint exists.
- **Source Verification and Trust Verification cannot be implemented as specified without live data.** `KNOWLEDGE_VALIDATION_SPEC.md §§ 4–5` call for re-fetching the actual cited source and reading `KNOWLEDGE_SOURCE_CATALOG.md`'s live Trust Score. Sprint 2 implements both gates' *logic* against injectable, fixture-backed lookups (a `SourceVerifier` protocol/`TrustScoreProvider` protocol the real Crawler/Catalog integration replaces later) — this is a deliberate seam, not a shortcut, but it means these two gates are the least "real" part of Sprint 2 and should be re-verified once live sources exist.
- **The Human Approval Gate's halt-then-explicit-restart design (§6) has no precedent in `PIPELINE_ENGINE.md`.** The frozen spec defines stage-level retry and whole-run rollback, but not a "pause a run indefinitely pending an external decision, then continue from a specific stage" primitive. Sprint 2's approach (halt the run, expose a separate resolve-and-restart-from-here entrypoint) is an implementation choice within the frozen contract's boundaries, not a Runtime change — but it is new ground, and should be reviewed specifically for whether it's the right shape before other future gates (if any) copy the pattern.
- **`Knowledge Conflict` artifacts and the Version Conflict Detection gate both reference `pending-conflict-resolution` status, but no artifact-status state machine currently exists in code.** `LIFECYCLE.md` (Sprint 1) defines Runtime/Module/PipelineRun state machines only — no `Artifact` lifecycle state machine. Sprint 2 will need a small, artifact-scoped status enum (`draft`, `validated`, `rejected`, `pending-conflict-resolution`, `pending-human-approval`, `superseded`) that does not currently exist anywhere in frozen architecture as an explicit state machine (the individual statuses are named across `KNOWLEDGE_VALIDATION_SPEC.md`, `KNOWLEDGE_ARTIFACTS.md`, and `KNOWLEDGE_CONFLICT_RESOLUTION.md` piecemeal, never assembled into one transition diagram) — Sprint 2 will assemble one, scoped narrowly to what Sprint 2 itself needs, and flag it for architecture review rather than treating it as already-frozen.

---

## 9. Dependencies

- **Sprint 1 Runtime (`v0.1.0-runtime-bootstrap`), unmodified.** `Module`, `ModuleManifest`, `Container`, `PluginRegistry`, `EventBus`, `PipelineEngine`/`PipelineDefinition`/`StageDefinition` — all consumed as-is; Sprint 2 adds no Runtime-level code.
- **No dependency on a real Crawler module.** Per [§8](#8-risks), Sprint 2 substitutes fixtures; this is a soft dependency in the sense that Sprint 2's extraction-rule *accuracy* cannot be fully validated until a Crawler exists, but it is not a hard blocker to writing and testing the pipeline mechanics.
- **No dependency on the Knowledge Graph, Embedding, or Retrieval modules.** Sprint 2's output (validated artifacts, resolved conflicts) is exactly the input those future modules will need, but none of their code is touched or assumed present.
- **Depends on `KNOWLEDGE_ARTIFACTS.md`, `KNOWLEDGE_EXTRACTION_SPEC.md`, `KNOWLEDGE_VALIDATION_SPEC.md`, `KNOWLEDGE_CONFLICT_RESOLUTION.md`, `MODULE_SYSTEM.md`, `PIPELINE_ENGINE.md`, `DEPENDENCY_INJECTION.md`, `EVENT_BUS.md`, and `STUDIO_EVENT_MODEL.md § 2`** remaining frozen for the duration of the Sprint — if any of these change mid-Sprint, the plan needs re-review before implementation continues.

---

## 10. Test Strategy

Following Sprint 1's existing pattern exactly (`tests/conftest.py`'s fully-isolated, `tmp_path`-scoped fixtures; no shared state; no execution-order dependence):

- **Artifact schema tests** — construction, validation-error cases (missing required envelope fields, empty `source_references` per the anti-hallucination check), serialization round-trips, for every in-scope artifact type.
- **Conflict resolution tests** — one test per named scenario in `KNOWLEDGE_CONFLICT_RESOLUTION.md`'s 5 named scenarios, plus explicit tests that the 9-level precedence hierarchy is applied in order, plus a test that a genuinely unresolvable case returns `Undecided` rather than guessing.
- **Validator gate tests** — one focused test suite per gate (8 suites), each testing pass/fail/edge behavior against fixture artifacts, including: schema failure routes to engineering triage not human approval; duplicate detection merges rather than rejects; version conflict creates a `Knowledge Conflict` and holds both artifacts; trust-below-threshold demotes rather than drops; engineering-review-contradiction escalates regardless of confidence; the four human-approval trigger conditions each independently route to the gate; confidence scoring's formula is exercised with known inputs/expected outputs.
- **Extractor tests** — extraction-rule tests for the in-scope source-type subset, plus Pattern Extraction's "recurring shape across ≥2 artifacts" logic specifically (a single-artifact input must never produce a Pattern).
- **Pipeline integration tests** — `knowledge.validation` and the in-scope `knowledge.graph_build` stages registered against a real `PipelineEngine` instance (same pattern as `tests/test_event_bus.py`/`test_lifecycle.py` exercising real Sprint 1 objects, not mocks) and run end-to-end against fixture `Knowledge Document`s, asserting final artifact status and that rollback/retry behave per `PIPELINE_ENGINE.md §§ 5–6` when a stage is made to fail.
- **Event publication tests** — asserting `ArtifactCreated`, `ConflictDetected`, `ValidationCompleted`, `HumanApprovalRequested`/`Resolved` are actually published to a real `EventBus` (per Sprint 1's existing `EventBus` test pattern) at the correct points, not merely that the pipeline runs.
- **No mocking of Sprint 1 Runtime primitives** — `Container`, `PipelineEngine`, `EventBus` are used for real in every test, consistent with this project's established testing discipline; only external-world seams (`SourceVerifier`, `TrustScoreProvider` per [§8](#8-risks)) are fixture-backed, because those are the actual boundary of what Sprint 2 can control.

---

## 11. Acceptance Criteria

1. `knowledge.validation` and `knowledge.graph_build` (Extraction, Pattern Extraction, Conflict Resolution stages) are registered `PipelineDefinition`s that run end-to-end against fixture input through a real `PipelineEngine`, producing a `PipelineRunResult` with `succeeded is True` for a clean-path fixture.
2. Every one of `KNOWLEDGE_VALIDATION_SPEC.md`'s eight gates is independently implemented, tested, and demonstrably enforces its documented fixed order (a test proves gate N+1 never runs if gate N fails, per `KNOWLEDGE_VALIDATION_SPEC.md § 0`).
3. `KNOWLEDGE_CONFLICT_RESOLUTION.md`'s precedence hierarchy is implemented such that all 5 named scenarios resolve exactly as documented, and a genuinely ambiguous case returns `Undecided` rather than an automatically-chosen winner.
4. No code path in Sprint 2 sets `Status: Stable` on an `Engineering Rule`, and no automated path advances a rule candidate past `Draft` — verified by an explicit test asserting this boundary, not merely by code review.
5. `ExtractorModule` and `ValidatorModule` both satisfy Sprint 1's `Module` ABC and pass `PluginRegistry` discovery/validation/instantiation unmodified — proven by a test that registers both through `PluginRegistry.discover()`/`register()`/`validate_dependencies()`/`instantiate()`, the same path Sprint 1's own plugin tests already exercise.
6. `pytest` passes in full (Sprint 1's 82 tests plus all new Sprint 2 tests), `mypy --strict` is clean, `ruff check`/`ruff format --check` are clean against new files (existing Sprint 1 formatting drift is not this Sprint's concern, per the precedent already set handling review comment #2).
7. Every event in [§5](#5-public-apis)'s "Events published" list is observed, in a test, actually arriving on a real `EventBus` subscription during a pipeline run.
8. The Sprint 2 risks in [§8](#8-risks) — especially the Validation-vs-Extraction ordering inconsistency and the split `knowledge.graph_build` definition — are written up in the end-of-Sprint report as open architectural questions for review, not silently resolved in code with no record.

---

## 12. Estimated File Structure

```
knowledge/
├── __init__.py
├── artifacts/
│   ├── __init__.py
│   ├── envelope.py          # common envelope (KNOWLEDGE_ARTIFACTS.md §1)
│   ├── document.py          # Knowledge Document
│   ├── api.py                # Knowledge API
│   ├── pattern.py            # Pattern / Anti-Pattern
│   ├── best_practice.py
│   ├── example.py
│   ├── workflow.py
│   └── conflict.py           # Knowledge Conflict
├── extraction/
│   ├── __init__.py
│   ├── module.py              # ExtractorModule (Module subclass)
│   ├── rules.py                # per-source-type extraction rules (in-scope subset)
│   └── pattern_extraction.py   # 2nd-pass pattern extraction
├── validation/
│   ├── __init__.py
│   ├── module.py               # ValidatorModule (Module subclass)
│   ├── gates.py                  # the eight gate stage callables
│   ├── approval.py               # PendingApproval / resolve() entrypoint
│   └── status.py                 # artifact status enum (per §8's risk item)
├── conflict/
│   ├── __init__.py
│   └── resolution.py            # 9-level precedence hierarchy + 5 named scenarios
└── pipelines/
    ├── __init__.py
    └── definitions.py            # knowledge.validation / knowledge.graph_build PipelineDefinitions

plugins/
├── extractor/
│   └── module.yaml
└── validator/
    └── module.yaml

tests/
├── knowledge/
│   ├── test_artifacts.py
│   ├── test_extraction.py
│   ├── test_pattern_extraction.py
│   ├── test_validation_gates.py
│   ├── test_conflict_resolution.py
│   ├── test_approval_gate.py
│   ├── test_pipeline_integration.py
│   └── test_event_publication.py
```

---

**End of plan.** No implementation, stubs, or code changes accompany this document. Awaiting review before any Sprint 2 code is written.
