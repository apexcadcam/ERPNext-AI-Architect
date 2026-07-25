# Sprint 9 Release Notes — Analysis Foundation

**Release:** `v0.10.0-analysis-foundation` (see Versioning Note below)
**Status:** Approved — all five phases passed implementation review; implementation frozen
**Branch:** `review/sprint9-analysis-foundation` — prepared and validated, **not merged into `main`, not tagged, not pushed**, per this release's own explicit instruction to prepare only
**Depends on (frozen, unmodified):** Sprint 1 Runtime, Sprint 2 Knowledge Factory, Sprint 3 Integration Layer, Sprint 4 Planning Engine, Sprint 5 Execution Engine, Sprint 6 Runtime Integration, Sprint 7 Goal Orchestration, Sprint 8 Intelligence Abstraction Layer (`v0.9.0-intelligence-abstraction`)
**Architecture reference:** Strategic Realignment v1/v2/v4 (the `analysis/` package framing — Question 1's "new layer between Requirements and Planning," Question 5's evidence-based `Recommendation` this Sprint's `SimilarityResult`/`GapAnalysis` feed into later)

---

## Versioning Note

The requested tag was `v1.0.0-analysis-foundation`. This project already has two tags at that exact major.minor.patch number — `v1.0.0` and `v1.0.0-architecture` — both from the original, much earlier "Architecture Freeze v1.0" milestone (the knowledge-base-only phase of this project, predating Sprint 1's Runtime work entirely; `v1.0.0` points to the commit *"declare Architecture Freeze v1.0, begin Phase 2 (Knowledge Engineering)"*). Reusing `v1.0.0` here would create two semantically unrelated tags sharing the same version number. Per the instruction's own "or the project's established versioning scheme if different," this release instead continues the unbroken `v0.1.0` → `v0.9.0` sequence Sprints 1–8 already established: **`v0.10.0-analysis-foundation`**.

## Summary

Sprint 9 builds `analysis/` — the deterministic layer the Strategic Realignment named as sitting between raw requirements and the Runtime's existing Planning/Execution/Orchestration/Intelligence machinery. Every phase was pure extraction or comparison: no LLM, no inference beyond mechanical field mapping, no recommendation, no Runtime wiring. Five phases, each independently reviewed and approved: foundational contracts → deterministic ERPNext metadata extraction → deterministic structured-requirement analysis → deterministic lexical similarity comparison → architecture protection and full pipeline validation. Sprint 9 modifies **zero existing files** — all 29 files across five phases are new (confirmed via `git diff main`: 3,681 insertions, 0 deletions), the same purely-additive profile every sprint since Sprint 7 has held.

## What Shipped

### Analysis Contracts (`analysis/contract.py`, Phase 1)

Twelve frozen, `extra="forbid"` data models: `Requirement`, `AnalysisContext`, `SupportingEvidence`, `Actor`, `BusinessEntity`, `BusinessProcess`, `BusinessRule`, `BusinessConstraint`, `RequirementAnalysis`, `SimilarityResult`, `GapAnalysis`, `AnalysisResult`. `SupportingEvidence` is deliberately richer than Sprint 8's `intelligence.contract.EvidenceItem` (`source_reference`/`excerpt`/`rationale` vs. an opaque `reference_id`/`summary`/`weight`) — the two types are independently owned by design and never merged, matching the same "each layer owns its own version of a shared concept" discipline Sprint 8 established for its own contracts.

### ERPNext Metadata Extraction (`analysis/erpnext/`, Phase 2)

Deterministic extractors for eight ERPNext metadata kinds (Modules, DocTypes, Fields, Workspaces, Reports, Workflows, Client Scripts, Server Scripts) into `BusinessEntity`/`BusinessProcess`/`BusinessRule`. Raw input models use `extra="ignore"` (not this project's own `extra="forbid"`) — a deliberate, disclosed distinction: these parse an external, uncontrolled schema. Disclosed gap: no `Actor` or `BusinessConstraint` is produced here — neither concept is naturally derivable from these eight metadata kinds without inventing a mapping that isn't there.

### Requirement Analysis (`analysis/requirements/`, Phase 3)

A second, independent extraction path — from already-structured requirement input (never free-form NLP, per this phase's own explicit boundary) to the identical canonical contract types Phase 2 produces. Six analyzer functions cover all six supported targets (Business Entities, Business Processes, Actors, Business Rules, Business Constraints, Requirements). Every produced fact's evidence traces back to a real, required `excerpt` in the raw input — there is no code path that can construct evidence without one.

### Similarity Analysis (`analysis/similarity/`, Phase 4)

Deterministic Jaccard-token-overlap comparison across all five supported kinds, plus `compare_analysis_result` — the function that takes the `AnalysisResult` Phase 3 always left with empty `similarity_results`/`gaps` and returns a new one with both populated, closing the loop Phase 3 explicitly deferred. Gap detection uses exactly one, disclosed, non-arbitrary threshold: a subject is a gap when its *maximum* score across every candidate is exactly `0.0`. The algorithm is deliberately shallow and lexical, not semantic — recognizing "Patient" and "Customer" as related is Sprint 8's `IntelligenceEngine`'s job, not this module's.

### Architecture Protection & Integration Validation (`tests/sprint9/`, Phase 5)

No production code. Converts every architectural rule from Phases 1–4 into an executable test — including a genuine cycle-detection pass over `analysis/`'s own internal import graph, not a hardcoded assumption — and a full, real, cross-phase pipeline test: structured requirement → `RequirementAnalyzer` → `AnalysisResult`; ERPNext metadata → `ERP Extractor` → `BusinessEntity`/`BusinessProcess`/`BusinessRule`; both → `Similarity Comparator` → `SimilarityResult`/`GapAnalysis`, run end to end with real fixtures.

## Architectural Decisions Made During Implementation

Three small, disclosed decisions surfaced by implementation, none requiring redesign:

- **`Actor`/`BusinessConstraint` are a content gap in Phase 2, not a design gap in Phase 4** — `compare_actors`/`compare_business_constraints` are fully implemented and tested using directly-constructed fixtures standing in for the ERPNext side, so the comparison capability is complete for all five kinds regardless of how far Phase 2's own extraction breadth has grown.
- **The similarity algorithm is lexical, never semantic, by design** — stated plainly in `comparator.py`'s own docstring as the precise boundary between this Sprint's Analysis layer and Sprint 8's Intelligence layer.
- **This release's versioning number** — see Versioning Note above.

## Public Interfaces

| Module | Key exports |
|---|---|
| `analysis.contract` | `Requirement`, `AnalysisContext`, `SupportingEvidence`, `Actor`, `BusinessEntity`, `BusinessProcess`, `BusinessRule`, `BusinessConstraint`, `RequirementAnalysis`, `SimilarityResult`, `GapAnalysis`, `AnalysisResult` |
| `analysis.erpnext` | `RawModule`, `RawDocType`, `RawField`, `RawWorkspace`, `RawReport`, `RawWorkflow`, `RawClientScript`, `RawServerScript` + `extract_module`/`extract_doctype`/`extract_fields`/`extract_workspace`/`extract_report`/`extract_workflow`/`extract_client_script`/`extract_server_script` |
| `analysis.requirements` | `RawRequirement` + five mention types + `analyze_business_entities`/`analyze_business_processes`/`analyze_actors`/`analyze_business_rules`/`analyze_business_constraints`/`analyze_requirement_statement`/`build_requirement_analysis`/`build_analysis_result` |
| `analysis.similarity` | `compare_business_entities`/`compare_business_processes`/`compare_actors`/`compare_business_rules`/`compare_business_constraints` + matching `detect_*_gaps` + `compare_analysis_result` |

## Test Statistics

| Suite | Tests |
|---|---|
| `tests/analysis/test_contract.py` | 67 |
| `tests/analysis/test_erpnext_extractor.py` | 37 |
| `tests/analysis/test_requirement_analyzer.py` | 38 |
| `tests/analysis/test_similarity_comparator.py` | 25 |
| `tests/sprint9/test_architecture_boundaries.py` | 12 |
| `tests/sprint9/test_end_to_end_pipeline.py` | 10 |
| **Sprint 9 total** | **189** |
| **Full repository regression suite** | **1,159 passed** |

## Coverage

```
Name                                Stmts   Miss Branch BrPart  Cover
analysis/__init__.py                    3      0      0      0   100%
analysis/contract.py                   73      0      0      0   100%
analysis/erpnext/__init__.py            4      0      0      0   100%
analysis/erpnext/extractor.py          31      0      0      0   100%
analysis/erpnext/metadata.py           62      0      0      0   100%
analysis/requirements/__init__.py       4      0      0      0   100%
analysis/requirements/analyzer.py      21      0      0      0   100%
analysis/requirements/raw.py           34      0      0      0   100%
analysis/similarity/__init__.py         3      0      0      0   100%
analysis/similarity/comparator.py      65      0     16      0   100%
TOTAL                                 300      0     16      0   100%
```

100% line and branch coverage, package-wide.

## Regression Review

- `mypy --strict`: clean across every file this Sprint added (the same 15 pre-existing findings in `tests/test_pipeline_engine.py`/`tests/test_event_bus.py` remain, confirmed via `git diff main` to be untouched by this Sprint, present on `main` since before Sprint 8)
- `ruff check`: clean
- `ruff format`: clean for every file this Sprint added (the same 9 pre-existing drift files remain, confirmed untouched)
- Full regression suite: **1,159 passed**, zero failures, zero skips

## Risks

- **Lexical-only similarity will under-match real, semantically-related concepts expressed in different vocabulary** — by design, not a defect (see Architectural Decisions above), but a real limitation until a future sprint wires this layer's output through Sprint 8's `IntelligenceEngine`.
- **`analysis/` has no Runtime consumer yet** — no `plugins/analysis/`, no capability registration. Proven, not merely stated: Phase 5's own boundary tests confirm no existing package (including `intelligence/`) imports `analysis` yet.
- **Phase 2's ERPNext extraction breadth is partial** — 8 metadata kinds, not the full range a real ERPNext instance exposes (e.g. Permissions/Roles, which would be `Actor`'s most natural real source).

## Technical Debt

None introduced. Both disclosed decisions (Actor/BusinessConstraint content gap; the similarity algorithm's lexical scope) were resolved and documented at the point of discovery, not deferred as unowned debt.

## Known Limitations

- Requirement input must already be structured (`RawRequirement` and its mention types) — this layer performs no NLP itself, by explicit Phase 3 scope.
- No semantic/embedding-based matching anywhere in `analysis/` — explicitly out of scope for the whole Sprint.
- No Knowledge Graph integration — `analysis/` and `knowledge/` remain mutually unaware of each other.
- No recommendation output — `SimilarityResult`/`GapAnalysis` are facts about overlap and absence, not judgments about what to do next.

## Next Sprint Readiness

Sprint 9 leaves three concrete, well-scoped directions open, none started:

1. **Wire `analysis/` into the Runtime** — an `AnalysisModule` mirroring `intelligence/module.py`'s exact shape (a Container capability, config-driven where relevant), the same kind of step Sprint 8 Phase 3 already proved out.
2. **Bridge Analysis and Intelligence** — a translation function from this Sprint's rich `SupportingEvidence` down to Sprint 8's simplified `EvidenceItem`, the exact seam both Sprint 8's and this Sprint's own docstrings already anticipated, letting `IntelligenceEngine.evaluate_tradeoff`/`challenge_assumptions` reason over `SimilarityResult`/`GapAnalysis` output for the first time.
3. **Broaden Phase 2's extraction breadth** — Roles/Permissions as a real source for `Actor`, closing the disclosed content gap.

## Confirmation

Sprint 9 is functionally complete and validated on `review/sprint9-analysis-foundation`: 1,159/1,159 tests passing, 100% line/branch coverage on `analysis/`, `mypy --strict` and `ruff` clean on every file this Sprint added, five phase-scoped commits plus this release-notes commit, zero existing files modified. **Not merged into `main`, not tagged, not pushed** — prepared only, exactly as instructed, pending explicit authorization to proceed.
