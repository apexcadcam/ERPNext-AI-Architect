# Sprint 22 Release Notes — Inheritance Resolution

**Release:** `v1.4.0` · **Status:** Implemented, validated, merged, and tagged.
**Depends on:** the Evidence Platform (`v1.1.0` Extraction, `v1.2.0` Aggregation, `v1.3.0` CLI)
**Architecture reference:** [Inheritance Resolution Specification](docs/evidence-platform/INHERITANCE_RESOLUTION_SPECIFICATION.md) · [ADR-0015](adr/ADR-0015-cross-repository-inheritance-resolution.md) · [RQ-0002](research/RQ-0002-controller-lifecycle-hook-population.md)
**Schema:** both producers move to `2.0`; the committed corpus is regenerated

---

## Summary

**The platform's one declared measurement gap is closed.**

From `v1.2.0` to `v1.3.0`, every `PatternSet` carried the same admission: 713 lifecycle-hook Evidence records existed — 237 in `frappe`, 476 in `erpnext` — and could not be turned into a measurement, because the collector emits a record only where a hook is *found*, so classes without hooks left no trace. The numerator existed; the population did not.

Sprint 22 supplies the population. `validate` is implemented by **31.6%** of frappe controllers and **35.3%** of ERPNext controllers. `categories_skipped` is `0`.

**The `SKIPPED` section is empty because the measurement exists, not because the declaration was withdrawn.** That distinction is the sprint.

## What Shipped

### Class-definition Evidence (`evidence/collectors.py`)

Two new categories. `class_definition` is emitted for **every** class, unconditionally, before any base is examined; `class_base_declaration` is emitted once per declared base, recording the name **exactly as written**.

They are a pair by design. A single category recording "class X declares base B" would emit nothing for a class with no bases — precisely the blind spot being fixed. Recording the node set and the edge set separately makes *every class produces at least one record* structural rather than remembered.

The collector **resolves nothing**: it does not follow imports, does not reconcile `Document` with `frappe.model.document.Document`, and does not distinguish a controller from an exception class. Reading `class SalesInvoice(SellingController)` it genuinely does not know, and a collector that guesses is one that can be wrong in a way nothing downstream can detect.

### The Inheritance Resolver (`aggregation/inheritance.py`)

An independent component, not a step inside aggregation. Pure, no I/O, no clock. A forward breadth-first sweep from the root, which makes three properties fall out of the algorithm's shape rather than being bolted on: cycles terminate by construction, chain depth is free, and recorded depths are shortest-path.

`descendants` contains **measured-corpus classes only**, so a supporting corpus can complete a chain without joining the population it completes.

### Cross-repository resolution

`AggregationRequest` gains `supporting_evidence_sets`. A supporting corpus contributes class definitions used to resolve inheritance and **nothing else** — never an occurrence, never population membership, never a `Pattern`.

`PatternSet` gains `ResolutionProvenance`, recording which corpora contributed, the strategy, and the unresolved residue.

## Architectural Decisions Made During Implementation

Recorded in full in the [Decision Log](docs/DECISION_LOG.md) (D11–D17). The four that changed the shape of the work:

- **Research first.** RQ-0002 measured both trees before any code was written, and found that inheritance crosses repository boundaries. That is a property of what one `EvidenceSet` may contain, not of the collector — it would otherwise have surfaced during implementation as a wrong number rather than a design question.
- **Extraction records facts; aggregation infers descent.** Resolving ancestry at extraction time would freeze an inference into a record that claims to state a fact, and would make extracting `erpnext` depend on `frappe` being checked out.
- **Structural categories sit outside the accounting.** Filing them as skipped would assert "we could not measure this" when nobody tried. A declared gap that is not a gap devalues the ones that are.
- **`aggregated + skipped == present` is a validator**, not a convention. It immediately caught a persistence fixture that had been internally inconsistent since it was written.

## Measured Results

| Repository | Controllers | `validate` | `on_submit` | Patterns |
|---|---|---|---|---|
| `frappe` v15.103.1 | **275** | 87 (31.6%) | — | 15 |
| `erpnext` v15.102.0 | **510** | 180 (35.3%) | 63 (12.4%) | 14 |

ERPNext's 510 requires `frappe` as resolution context; alone it resolves 492. **18 of its controllers reach `Document` only through a frappe-defined base** (`NestedSet`, `WebsiteGenerator`).

## Validation

Regression — nothing that existed moved:

| Check | Result |
|---|---|
| frappe `frappe.whitelist` | 518/520 ✅ |
| frappe `validate_and_sanitize_search_inputs` | 15/520 ✅ |
| erpnext `frappe.whitelist` | 705/705 ✅ |
| erpnext `validate_and_sanitize_search_inputs` | 59/705 ✅ |
| Existing `pattern_id` | unchanged ✅ |
| v1.3.0 `evidence_id` values | all 2,057 present ✅ |
| Existing pattern ordering | unchanged ✅ |

Independent confirmation: the resolver reproduces RQ-0002's 275 / 492 / 510 and max depth 6 — via a forward BFS, where the research used a backward DFS. Two algorithms, same numbers.

**2,389 tests pass.** 100% coverage on `evidence/` and `aggregation/`. `mypy --strict` clean on every file this sprint touched; `ruff check` clean.

## Known Limitations

1. **The CLI cannot supply a supporting corpus.** No `--supporting` flag exists, so the committed ERPNext `PatternSet` — correctly at 510 — was produced through the API. `ResolutionProvenance` records its inputs, so it is reproducible, but not yet by the shipped CLI. **This is the first thing to fix.**
2. **`schema_version` is written by both engines and checked by no reader.** A bump is a label, not a gate. An old reader rejects a `2.0` artifact because of `extra="forbid"` and a closed enum — the right outcome for an incidental reason.
3. **Two repositories only.** `CanonicalRepository` remains a closed enum ([W3](docs/evidence-platform/BACKLOG.md#w3--hrms-support)).
4. **Evidence artifacts are still not byte-reproducible** — `collected_at` per record ([W4](docs/evidence-platform/BACKLOG.md#w4--timestamp-reproducibility-decision)).
5. **Repository-wide `mypy --strict` and `ruff format` remain unclean** in pre-existing Sprint 1 files ([W1](docs/evidence-platform/BACKLOG.md#w1--repository-wide-typing-cleanup), [W2](docs/evidence-platform/BACKLOG.md#w2--repository-wide-formatting-normalization)).

## Follow-up Work

- **`architect patterns aggregate --supporting frappe:v15.103.1`**, then regenerate the corpus through the CLI so the artifacts are reproducible by the tool users actually run.
- **Sprint 23 — Candidate Rules.** Now genuinely possible: a measured hook-implementation rate is the kind of evidence a Rule can cite. Promotion still passes through the human review gate ADR-0002 requires.
- **`schema_version` enforcement**, or a recorded decision that it is documentation only.
- **W1–W4** in the [backlog](docs/evidence-platform/BACKLOG.md), unchanged by this sprint.

## A Note on Method

This sprint is the clearest instance of the discipline the project was built around, so it is worth stating plainly.

The gap was **declared for two releases** rather than papered over. It was **investigated by measurement** before implementation, not argued about. The research **found a constraint nobody had anticipated** — cross-repository inheritance — early enough that it became a design decision instead of a wrong number. And the declaration was **earned out**, not deleted: a test would have failed had the row simply been removed.

The platform said what it could not measure, and then measured it.
