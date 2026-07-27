# Sprint 10 Release Notes — Knowledge Foundation

**Release:** `v0.11.0-knowledge-foundation` (see Versioning Note below)
**Status:** Approved — all five phases (contracts, builder, projection, query, validation) passed implementation review; implementation frozen
**Branch state:** prepared, **not committed to a dedicated branch, not merged into `main`, not tagged, not pushed** — Sprint 10's own files currently sit as uncommitted working-tree changes on top of `review/sprint9-analysis-foundation` (see Branch & Merge Note below)
**Depends on:** `analysis.contract` (Sprint 9, `analysis/contract.py`) — itself still unreleased; frozen unmodified: Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer, Sprint 4 Planning Engine, Sprint 5 Execution Engine, Sprint 6 Runtime Integration, Sprint 7 Goal Orchestration, Sprint 8 Intelligence Abstraction
**Architecture reference:** `adr/ADR-001-analysis-knowledge-direction.md` — Requirements → Analysis → Knowledge → Intelligence → Planning → Execution is this project's single authoritative dependency direction as of this Sprint

---

## Versioning Note

Sprint 9 (`analysis/`) was prepared but never tagged — it sits, unreleased, on `review/sprint9-analysis-foundation` as `v0.10.0-analysis-foundation` (recommended, not yet created). Continuing that same unbroken `v0.1.0` → `v0.9.0` sequence, Sprint 10 is next at `v0.11.0`.

The suffix is deliberately **not** `knowledge-factory` — that name is already taken by `v0.2.0-knowledge-factory` (Sprint 2's `knowledge.artifacts`/`knowledge.graph`/`knowledge.conflict`/`knowledge.validation`/`knowledge.extraction`, all reused, unmodified, by this Sprint). Reusing it here would imply Sprint 10 replaces or re-does that work, when it in fact builds a new layer (`knowledge.domain`/`builder`/`projection`/`query`) on top of it. `knowledge-foundation` names this Sprint's own, distinct contribution: the domain-model foundation ADR-001 calls for.

## Summary

Sprint 10 builds the Knowledge layer ADR-001 names as sitting between Analysis and Intelligence: `knowledge.domain` (immutable contracts), `knowledge.builder` (deterministic `AnalysisResult → KnowledgeSnapshot` transformation), `knowledge.projection` (deterministic conversion into Sprint 2's existing graph contracts), and `knowledge.query` (a read-only, in-memory query service). Every stage is pure, non-AI transformation — no reasoning, no recommendation, no persistence, no graph database, no networking. Five phases, each independently reviewed and approved. Sprint 10 modifies **one** pre-existing file (`tests/sprint9/test_architecture_boundaries.py`, twice, both disclosed, narrow generalizations of its sanctioned-consumer list — Sprint 9's own behavior is unchanged); every other file — 19 across production and tests — is new.

## What Shipped

### Knowledge Domain Contracts (`knowledge/domain/`, Phase 1)

Six new frozen, `extra="forbid"` models — `KnowledgeReference`, `KnowledgeCollection`, `KnowledgeSnapshot`, `KnowledgeQuery`, `KnowledgeResult`, `KnowledgeStatistics` — reusing Sprint 2's existing `ContentArtifact`/`ArtifactType`/`GraphNode`/`GraphEdge` rather than duplicating them. `KnowledgeReference.subject_kind` is a closed `Literal` mirroring Analysis's own five fact kinds, a disclosed and deliberate coupling (see the Phase 1 architectural clarification on file) favoring auditability over speculative generality.

### Knowledge Builder (`knowledge/builder/`, Phase 2)

Deterministic transformation from `AnalysisResult` into Phase 1's contracts. Disclosed gap: only `BusinessProcess` maps onto a real `ContentArtifact` (`Workflow`) — `BusinessEntity`/`BusinessRule`/`BusinessConstraint`/`Actor` have no honest fit in Sprint 2's closed `ArtifactType` vocabulary, so they are represented only via `KnowledgeReference`, never forced into a artifact shape that doesn't fit.

### Knowledge Graph Projection (`knowledge/projection/`, Phase 3)

Deterministic conversion of Knowledge domain objects into Sprint 2's existing `GraphNode`/`GraphEdge` contracts — no new graph vocabulary introduced. Sprint 2's own `GraphBuilder` was reviewed and found unusable here (it requires a live store and a `VALIDATED` status precondition neither of which this storeless, in-memory stage has); its edge-derivation logic was mirrored, not reused directly, and that reasoning is disclosed in the module.

### Knowledge Query Service (`knowledge/query/`, Phase 4)

A read-only, in-memory `KnowledgeQueryService` over one `KnowledgeSnapshot`. Every method maps directly onto one of `KnowledgeCollection`'s own four existing fields (`artifacts`/`nodes`/`edges`/`references`) or `KnowledgeStatistics` — no invented API surface.

### Quality & Architecture Validation (`tests/sprint10/`, Phase 5)

No production code. `test_architecture_boundaries.py` (18 tests) proves the precise, ADR-001-sanctioned import boundary: only `knowledge.domain` and `knowledge.builder` may import `analysis`; `knowledge.projection`/`knowledge.query` never do, even transitively outside that one approved chain; no graph database, networking, or provider SDK anywhere in the layer. `test_end_to_end_pipeline.py` (16 tests) exercises the real, unmocked chain `AnalysisResult → Builder → Projection → Query`, proving determinism, idempotency (including re-projecting already-projected output), no stage mutating a prior stage's output, and absence of caching or shared mutable state.

## Architectural Decisions Made During Implementation

- **The literal instruction "Builder is the only component allowed to consume `AnalysisResult`" does not hold against Phase 1's own approved design** — `KnowledgeSnapshot.source: AnalysisResult` was approved in Phase 1 itself. Phase 5 tests the boundary that decision actually implies (domain + builder sanctioned; projection + query forbidden) rather than silently breaking Phase 1's design or ignoring the instruction. Disclosed at Phase 5, not silently resolved.
- **`Actor`/`BusinessEntity`/`BusinessRule`/`BusinessConstraint` have no `ContentArtifact` shape** — resolved identically at both Phase 2 and Phase 3 by representing them only via `KnowledgeReference`, never inventing a parallel artifact vocabulary to force a fit.
- **This release's version suffix** — see Versioning Note above.

## Public Interfaces

| Module | Key exports |
|---|---|
| `knowledge.domain` | `KnowledgeReference`, `KnowledgeCollection`, `KnowledgeSnapshot`, `KnowledgeQuery`, `KnowledgeResult`, `KnowledgeStatistics` |
| `knowledge.builder` | `build_entity_references`, `build_process_references`, `build_rule_references`, `build_constraint_references`, `build_actor_references`, `build_workflow_artifacts`, `build_knowledge_collection`, `build_knowledge_snapshot` |
| `knowledge.projection` | `project_artifact`, `project_artifact_edges`, `project_collection`, `project_snapshot` |
| `knowledge.query` | `KnowledgeQueryService` |

## Test Statistics

| Suite | Tests |
|---|---|
| `tests/knowledge/domain/test_contract.py` | 48 |
| `tests/knowledge/builder/test_builder.py` | 22 |
| `tests/knowledge/projection/test_projector.py` | 26 |
| `tests/knowledge/query/test_service.py` | 33 |
| `tests/sprint10/test_architecture_boundaries.py` | 18 |
| `tests/sprint10/test_end_to_end_pipeline.py` | 16 |
| **Sprint 10 total** | **163** |
| **Full repository regression suite** | **1,324 passed** |

## Coverage

```
Name                              Stmts   Miss  Cover
knowledge/domain/__init__.py          3      0   100%
knowledge/domain/contract.py         51      0   100%
knowledge/builder/__init__.py         3      0   100%
knowledge/builder/builder.py         29      0   100%
knowledge/projection/__init__.py      3      0   100%
knowledge/projection/projector.py    19      0   100%
knowledge/query/__init__.py           3      0   100%
knowledge/query/service.py           58      0   100%
```

100% line coverage on every package Sprint 10 added. (Package-wide `knowledge/` total is 98% — the remaining gaps are all in pre-existing Sprint 2/3 modules — `conflict`, `extraction`, `validation`, `graph.store` — untouched by this Sprint.)

## Regression Review

- `mypy --strict`: clean on all 8 production files and all 26 test files this Sprint added
- `ruff check`: clean
- `ruff format`: clean (one formatting fix applied during Phase 5 to `tests/sprint9/test_architecture_boundaries.py`'s own modified section, verified against the full suite afterward)
- Full regression suite: **1,324 passed**, zero failures, zero skips

## Branch & Merge Note

Unlike Sprint 9's release preparation, Sprint 10's files were never assembled into their own phase-scoped commits or a dedicated `review/sprint10-*` branch — this phase's instructions asked for a release **review**, not a git operation, so none was performed. Concretely, right now:

- All 8 production files, 11 test files, and `adr/ADR-001-analysis-knowledge-direction.md` are **uncommitted** in the working tree.
- They sit on top of `review/sprint9-analysis-foundation`, which is itself **not merged into `main`**.

This means Sprint 10 cannot actually be merged into `main` yet in the literal sense — there is no Sprint 10 branch, and its prerequisite (Sprint 9) isn't merged either. See the Final Statement below for what "approved" means given this state.

## Risks

- **No Runtime consumer yet** — no capability registration, no `plugins/knowledge/`. Proven, not merely stated: Phase 5's own boundary tests confirm no existing package outside Knowledge imports any of the four new subpackages yet.
- **Workflow is the only populated `ContentArtifact` kind** — `BusinessEntity`/`BusinessRule`/`BusinessConstraint`/`Actor` remain reference-only until a future sprint either extends `ArtifactType`'s vocabulary or a redesign decides they should stay reference-only permanently (an open question, not resolved by this Sprint).
- **Sprint 10 depends on an unreleased Sprint 9** — any change to `analysis.contract` before Sprint 9 is actually released could still ripple into `knowledge.domain`/`knowledge.builder`.

## Technical Debt

- **Documentation Update Plan (produced before Sprint 10 began) is still unapplied** — the Strategic Realignment documents themselves have not yet been edited to reflect ADR-001's Analysis → Knowledge direction; the plan identifying exactly what to change exists, but applying it was explicitly out of scope for every phase since.
- **No git release artifacts for Sprint 10** — no dedicated branch, no phase-scoped commit history, no tag. Deferred pending explicit instruction (see Branch & Merge Note).
- **`ArtifactType`'s closed vocabulary still has no shape for `business_entity`/`business_rule`/`business_constraint`/`actor`** — carried over from Sprint 9/Phase 2's own disclosed gap, still unresolved, not worsened by this Sprint.

## Future ADR Candidates

- Whether `business_entity`/`business_rule`/`business_constraint`/`actor` should ever get their own `ContentArtifact` shape, or whether reference-only representation is the permanent, intended design — currently an open question, not a decision.
- How Knowledge should be exposed to the Runtime (a `KnowledgeModule` capability, mirroring `intelligence/module.py`'s and Sprint 9's own recommended-but-unstarted `AnalysisModule` shape) — not started, no design decision made yet.

## Known Limitations

- `knowledge.query.KnowledgeQueryService` scopes to exactly one `KnowledgeSnapshot` per instance — querying across multiple accumulated snapshots is out of scope.
- No indexing, no caching, no graph traversal — every query is a linear scan, by design, over data already in memory.
- No persistence anywhere in the layer — a `KnowledgeSnapshot` exists only as long as its caller holds a reference to it.

## Confirmation

Sprint 10 is functionally complete and validated: 1,324/1,324 repository tests passing, 100% coverage on every package this Sprint added, `mypy --strict` and `ruff` clean on every file this Sprint added, exactly one pre-existing file touched (a disclosed, narrow test-boundary generalization, twice). **Not committed to a dedicated branch, not merged into `main`, not tagged, not pushed** — reviewed only, exactly as this phase's own instructions asked, pending explicit authorization to proceed to actual release mechanics.
