# Sprint 22 Release Notes — Inheritance Resolution

**Two releases.** Sprint 22 shipped once, was found to contain a semantic defect, and is being corrected.

| Release | Commit | State | `frappe` `validate` |
|---|---|---|---|
| **`v1.4.0`** | `189090a` | Tagged and historical. **Contains the numerator-membership defect.** | `87/275` |
| **`v1.4.1`** | pending | Corrective. Not yet tagged. | **`84/275` ≈ 30.5%** |

`v1.4.0` is **not** rewritten. It records what was actually released, including a measurement later found to be wrong. Section [The v1.4.1 correction](#the-v141-correction) states the current figures; everything above it describes Sprint 22 as `v1.4.0` shipped it.

> **If you are reading for the current measurement, `frappe` `validate` is `84/275`.** The `87/275` below is historical and superseded.

**Depends on:** the Evidence Platform (`v1.1.0` Extraction, `v1.2.0` Aggregation, `v1.3.0` CLI)
**Architecture reference:** [Inheritance Resolution Specification](docs/evidence-platform/INHERITANCE_RESOLUTION_SPECIFICATION.md) · [ADR-0015](adr/ADR-0015-cross-repository-inheritance-resolution.md) · [RQ-0002](research/RQ-0002-controller-lifecycle-hook-population.md)
**Schema:** both producers move to `2.0`; the committed corpus is regenerated

---

## Summary

**The platform's one declared measurement gap is closed.**

From `v1.2.0` to `v1.3.0`, every `PatternSet` carried the same admission: 713 lifecycle-hook Evidence records existed — 237 in `frappe`, 476 in `erpnext` — and could not be turned into a measurement, because the collector emits a record only where a hook is *found*, so classes without hooks left no trace. The numerator existed; the population did not.

Sprint 22 supplies the population. As released at `v1.4.0`, `validate` was reported as **31.6%** of frappe controllers and **35.3%** of ERPNext controllers. `categories_skipped` is `0`.

> **Superseded for frappe.** The frappe figure was computed against a numerator that included classes outside the population; the corrected value is **30.5%** (`84/275`). The ERPNext figure was and remains correct. See [The v1.4.1 correction](#the-v141-correction).

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

**As released at `v1.4.0` — the frappe row is superseded:**

| Repository | Controllers | `validate` | `on_submit` | Patterns |
|---|---|---|---|---|
| `frappe` v15.103.1 | **275** | ~~87 (31.6%)~~ → **84 (30.5%)** | — | 15 |
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

**2,389 tests passed at `v1.4.0`**; the current suite at `HEAD` is **2,414**. 100% coverage on `evidence/` and `aggregation/`. `mypy --strict` clean on every file this sprint touched; `ruff check` clean.

## The v1.4.1 correction

**Status: pending. Not tagged, not released.**

### The defect

`CONTROLLER_LIFECYCLE_HOOK` derived its denominator from the resolved `Document`-descendant population, but its numerator from *every* lifecycle-hook record. Nothing constrained the second to the first, so `support` was a ratio between two different sets.

A hook record says a class defines a method named `validate` or `on_update`. It does not say the class is a controller — and three frappe classes proved the difference: `DBTable`, `EMail` and `NamingSeries` each define a method called `validate` while descending from nothing.

### The invariant now enforced

```
occurrence_symbols ⊆ population_symbols
    ⇒  0 ≤ occurrences ≤ population  ⇒  0 ≤ support ≤ 1
```

Enforced by construction before grouping. **Clamping `support` to `1.0` was explicitly rejected** — it would have satisfied the constraint while leaving the measurement wrong. Full statement: [Aggregation §5.1](docs/evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md); decision and discovery: [D18](docs/DECISION_LOG.md); Sprint 22 spec: [§4.4](docs/evidence-platform/INHERITANCE_RESOLUTION_SPECIFICATION.md).

### Corrected measurements

| | `v1.4.0` | `v1.4.1` |
|---|---|---|
| `frappe` controller population | 275 | **275** — unchanged |
| `frappe` `validate` | 87/275 (31.6%) | **84/275 ≈ 30.5%** |
| `frappe` other lifecycle subjects | — | **all unchanged** |
| `erpnext` controller population | 510 | **510** — unchanged |
| `erpnext` `validate` | 180/510 | **180/510** — unchanged |
| `frappe` whitelist | 518/520 · 15/520 | **unchanged** |
| `erpnext` whitelist | 705/705 · 59/705 | **unchanged** |

**ERPNext was already correct**, and not by luck: all 196 of its hook-bearing classes resolve into the 510 once `frappe` is supplied as context, so the filter removes nothing. The 18 that fail to resolve *without* `frappe` are exactly the ones `--supporting` recovers.

### Validation at `HEAD`

**2,414 tests pass.** 100% coverage on `evidence/` and `aggregation/` — 687 statements, zero missed. `mypy --strict` clean across the sprint's 68 files; `ruff check` clean. The membership invariant is verified from the persisted artifacts against source Evidence across all 29 published Patterns. CLI/API parity re-confirmed: both artifacts regenerate byte-for-byte through the public CLI.

### How it was found

By **Commit 6's consumer validation**, before the corrective release rather than after it — the first fixture written for the new `--supporting` flag made aggregation fail outright. The second time in this platform's history that a consumer surfaced what full coverage did not; the first was the denominator gap itself.

## Known Limitations

1. ~~**The CLI cannot supply a supporting corpus.**~~ **Closed.** `--supporting <repository>:<version>` was added in Commit 6; both committed artifacts now regenerate byte-for-byte through the public CLI.
2. **`schema_version` is written by both engines and checked by no reader.** A bump is a label, not a gate. An old reader rejects a `2.0` artifact because of `extra="forbid"` and a closed enum — the right outcome for an incidental reason.
3. **Two repositories only.** `CanonicalRepository` remains a closed enum ([W3](docs/evidence-platform/BACKLOG.md#w3--hrms-support)).
4. **Evidence artifacts are still not byte-reproducible** — `collected_at` per record ([W4](docs/evidence-platform/BACKLOG.md#w4--timestamp-reproducibility-decision)).
5. **Repository-wide `mypy --strict` and `ruff format` remain unclean** in pre-existing Sprint 1 files ([W1](docs/evidence-platform/BACKLOG.md#w1--repository-wide-typing-cleanup), [W2](docs/evidence-platform/BACKLOG.md#w2--repository-wide-formatting-normalization)).

## Follow-up Work

- ~~`architect patterns aggregate --supporting frappe:v15.103.1`~~ — **done in Commit 6**; the corpus is reproducible through the CLI.
- **Tag `v1.4.1`** once the release review passes.
- **Sprint 23 — Candidate Rules.** Now genuinely possible: a measured hook-implementation rate is the kind of evidence a Rule can cite. Promotion still passes through the human review gate ADR-0002 requires.
- **`schema_version` enforcement**, or a recorded decision that it is documentation only.
- **W1–W4** in the [backlog](docs/evidence-platform/BACKLOG.md), unchanged by this sprint.

## A Note on Method

This sprint is the clearest instance of the discipline the project was built around, so it is worth stating plainly.

The gap was **declared for two releases** rather than papered over. It was **investigated by measurement** before implementation, not argued about. The research **found a constraint nobody had anticipated** — cross-repository inheritance — early enough that it became a design decision instead of a wrong number. And the declaration was **earned out**, not deleted: a test would have failed had the row simply been removed.

The platform said what it could not measure, and then measured it.
