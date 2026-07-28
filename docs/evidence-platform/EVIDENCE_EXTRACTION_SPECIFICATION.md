# EVIDENCE EXTRACTION ENGINE — ARCHITECTURE SPECIFICATION

**Version:** 1.1
**Status:** Ratified and implemented. Released as `v1.1.0`.
**Package:** [`evidence/`](../../evidence/)

> **Provenance of this document.** This specification was written and approved during Sprint 20, before implementation, and every section number cited throughout `evidence/` refers to it. It was committed to the repository on 2026-07-28, after the fact — the code and its tests entered the repository first. Where this document and the code disagree, **the code and its tests are authoritative**; §16 records the one place they knowingly differ.

---

## 1. Purpose

This project does not learn from a language model. It learns from verifiable evidence extracted from the ERPNext ecosystem, with every architectural conclusion traceable back to its source.

This engine is the first half of that sentence. It reads pinned, read-only checkouts of canonical Frappe repositories and emits structured records of what is *actually there* — each one carrying the repository, version, commit, file, and line it came from. It makes no judgement, computes no score, and calls no language model.

## 2. Canonical repositories

Extraction targets a **closed set** of pinned, read-only canonical references:

| Value | Repository |
|---|---|
| `frappe` | `frappe/frappe` |
| `erpnext` | `frappe/erpnext` |

Implemented as `evidence.contract.CanonicalRepository`, a closed enum. Adding a member is a contract change requiring its own review.

`version` and `commit` are **caller-supplied and never auto-detected**. This keeps the engine free of a `git` runtime dependency and makes provenance an explicit, testable input rather than an ambient property of the machine that happened to run it. A stored `EvidenceSet` always states which revision it describes.

## 3. Signal types

Version 1 recognises exactly **two** categories, deliberately:

| Category | What one record means |
|---|---|
| `controller_lifecycle_hook` | A method on a class, whose name is a recognised Frappe `Document` lifecycle hook |
| `whitelisted_api_decoration` | One decorator applied to one function that carries a whitelist-family decorator |

### 3.1 Recognised lifecycle hook names

A fixed, closed list. A method named anything else is not evidence of a lifecycle hook, and no record is emitted for it. The authoritative list lives in `evidence/collectors.py`.

## 4. Non-goals

Explicitly out of scope for this engine and this schema:

- **Aggregation of any kind** — counting, ratios, populations, frequency. That is the Pattern Aggregation Engine.
- **Any relationship between Evidence records** — grouping, ranking, correlation.
- **Any confidence, severity, priority, or recommendation field.**
- **Other frameworks** (Django, Odoo, …). Not a goal of this Sprint or this schema.
- **Any Reasoning Engine / LLM call.** Zero, at any point.

## 5. Design principles

1. **Atomic Evidence.** One record per single observed fact. A function carrying three decorators produces three records, never one bundled record with a composite subject. This is what later makes distinct-symbol counting cheap and honest.
2. **Read-only.** The engine never writes to a canonical source tree. Consequently the Module declares no `rollback_capability` — there is nothing to compensate.
3. **Total traceability.** A record carries a real repository, version, commit, file, and line. A finding that cannot be traced this precisely is not emitted.
4. **No scoring.** No `confidence` field of any kind exists in this contract.

## 6. Contract

Every model is frozen (`ConfigDict(frozen=True, extra="forbid")`). Full definitions: [`evidence/contract.py`](../../evidence/contract.py).

| § | Type | Notes |
|---|---|---|
| 6.1 | `CanonicalRepository` | §2's closed set |
| 6.2 | `EvidenceKind` | Closed vocabulary; `implementation` only. `documentation` / `migration` / `release_note` / `architecture_decision` are deliberately **not** stubbed — each is added only when its own Miner actually exists |
| 6.3 | `EvidenceCategory` | §3's two categories |
| 6.4 | `CollectorName` | Closed vocabulary for `Evidence.collector`, not a free string |
| 6.5 | `Source` | Mandatory provenance: repository, version, commit, relative path, line |
| 6.6 | `Evidence` | One atomic observed occurrence |
| 6.7 | `EvidenceExtractionRequest` | The Input. Carries `max_files` and `timeout_seconds` as explicit bounds |
| 6.8 | `EvidenceStatistics` | Files examined / skipped / failed, evidence extracted |
| 6.9 | `EvidenceExtractionError` | One file that failed to parse. See §8 |
| 6.10 | `EvidenceSet` | The final artifact. `schema_version` is `"1.0"` for this contract shape |

### `evidence_id` — content-addressed identity

`sha256(repository | relative_path | line | category | symbol | subject)`.

Deterministic and content-addressed, which enables direct cross-run and future cross-version comparison. Contrast `evidence_set_id`, which is a fresh UUID per *run* — identity of the observation versus identity of the act of observing.

## 7. Collectors

Two, one per category. Both walk this package's own contracts and emit atomic Evidence (§3, §5). Neither aggregates, compares, or scores anything.

- **`collect_controller_lifecycle_hook_evidence`** — class-membership aware; a hook name at module level is not a controller hook.
- **`collect_whitelisted_api_decoration_evidence`** — one record per decorator on a whitelisted function.

## 8. Extraction algorithm, and graceful degradation

1. Resolve a filesystem connector for `source_root`.
2. Walk the tree, bounded by `max_files` and `timeout_seconds`; hitting the file ceiling sets `truncated` and is reported, never silent.
3. Parse each `.py` file to an AST.
4. Run both collectors over it.
5. Sort (§9).
6. Assemble the `EvidenceSet`.

**A file that fails to parse does not fail the run.** It becomes an `EvidenceExtractionError` record inside the returned `EvidenceSet` — a first-class result, persisted and assertable, never a log line and never a raised exception. Extraction still completes.

## 9. Determinism and ordering

Two runs against the same tree produce an identical `EvidenceSet` in every field — including every `evidence_id` — except `evidence_set_id` and the timestamps. Ordering is established here, deterministically, and no downstream layer may re-derive or "helpfully" re-sort it.

## 10. Persistence

JSONL for records plus a JSON sidecar for metadata, written with `sort_keys=True` so repeated writes of the same content are byte-identical and reviewable under `git diff`. Chosen over SQLite/DuckDB/Postgres: the corpus is small, the artifact is a reviewable input to an argument, and a database would make the evidence harder to inspect than the code it describes.

`read_evidence_set` is the exact inverse of `write_evidence_set`, and converts every malformed-input error into `EvidenceError_` so a caller only ever catches this package's own exception type.

## 11. Module and plugin

Standard Module shape, registered as plugin `evidence`. `capabilities_required` is empty; no `rollback_capability` (§5).

## 12. Architecture boundaries

- No frozen package imports `evidence`, with exactly one named exception recorded in the boundary test itself.
- `evidence` imports no Repository Intelligence package (`discovery` / `synthesis` / `evaluation` / `recommendation`) and none of them imports `evidence` — separate lineages.
- No LLM or provider library, anywhere.
- No new third-party dependency beyond `pydantic`.

Enforced by [`tests/evidence/test_architecture_boundaries.py`](../../tests/evidence/test_architecture_boundaries.py) via AST scanning plus subprocess `sys.modules` inspection.

## 13. Testing

100% statement coverage is required. Unreachable defensive branches carry `# pragma: no cover` with a written justification; reachable ones get real tests. Boundary tests run against the real source tree, not a fixture of it.

## 14. Measured envelope

Against the real trees, at the released version:

| Repository | Files examined | Files failed | Evidence |
|---|---|---|---|
| `frappe` v15.103.1 | 46,296 | 0 | 812 |
| `erpnext` v15.102.0 | 5,938 | 0 | 1,245 |

Zero parse failures on either tree.

## 15. Public API

`extract_evidence(request: EvidenceExtractionRequest) -> EvidenceSet` — the one public entry point, composing §8's steps.

## 16. Known deltas between this document and the code

- **None outstanding.** One was found during production validation and resolved in the engine's favour: an independent `grep` counted 519 `@frappe.whitelist` occurrences in `frappe` where the engine emitted 518. The extra occurrence is inside a docstring at `frappe/__init__.py:833` — a usage example in `whitelist()`'s own documentation. The AST-based collector correctly excludes it. **The engine was right and the grep was wrong**; no code changed.
- **Reproducibility caveat.** Re-extraction reproduces every `evidence_id` and every non-timestamp field identically and in identical order, but the persisted JSONL is *not* byte-identical, because each record carries a `collected_at` wall-clock timestamp. This is consistent with §9, which exempts timestamps, but it does mean a re-extraction shows every line as changed under `git diff`. Recorded as a known limitation, not a defect.
