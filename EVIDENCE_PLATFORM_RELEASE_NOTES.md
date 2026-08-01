# Evidence Platform Release Notes — Sprints 20, 21 and the CLI

**Releases:** `v1.1.0` (Evidence Extraction), `v1.2.0` (Pattern Aggregation), `v1.3.0` (CLI)
**Status:** Released and merged. This document records the platform through `v1.3.0`; Sprint 22 is
documented separately in [`SPRINT22_RELEASE_NOTES.md`](SPRINT22_RELEASE_NOTES.md).
**Architecture reference:** [`docs/evidence-platform/`](docs/evidence-platform/) — three specifications, committed with this document
**Frozen and unmodified:** Sprint 1 Runtime (except the disclosed CLI additions below), Sprints 2–15, and the Repository Intelligence Platform (`discovery`/`synthesis`/`evaluation`/`recommendation`, `v1.1.0-repository-intelligence`)

---

## Documentation Note

These three sprints were specified, reviewed, and approved in full before implementation, but the specifications themselves lived outside the repository until now. Every `§`-numbered reference in `evidence/`, `aggregation/`, `runtime/cli.py`, and `composition_root/evidence_platform.py` pointed at a document a reader could not open.

This release closes that gap. The three specifications are now committed under [`docs/evidence-platform/`](docs/evidence-platform/), each carrying a provenance header stating it was committed after the code, and each ending with a **Known Deltas** section recording every place the implementation knowingly departed from the approved design. Those deltas are recorded rather than edited away.

## Summary

This is the platform that makes the project's central claim enforceable rather than aspirational: *architectural knowledge comes from verifiable evidence extracted from the ERPNext ecosystem, not from a language model.*

**Zero Reasoning Engine calls exist anywhere in either engine**, asserted by boundary tests that scan for provider imports. Extraction reads ASTs; aggregation counts. Neither asks anything.

## What Shipped

### Evidence Extraction Engine (`evidence/`, `v1.1.0`)

Reads pinned, read-only checkouts of `frappe` and `erpnext` and emits atomic Evidence — one record per single observed fact, each carrying repository, version, commit, file, and line. Two collectors: controller lifecycle hooks, and whitelisted-API decoration.

`evidence_id` is content-addressed (`sha256` over the observation itself), so identity survives across runs and future versions, while `evidence_set_id` is a fresh UUID per run — identity of the observation versus identity of the act of observing.

A file that fails to parse becomes a persisted `EvidenceExtractionError` inside the returned artifact. Extraction still completes.

**Measured:** 46,296 files examined in `frappe` → 812 Evidence; 5,938 in `erpnext` → 1,245. **Zero parse failures on either tree.**

### Pattern Aggregation Engine (`aggregation/`, `v1.2.0`)

Consumes the *persisted* `EvidenceSet` — never re-runs extraction, never touches a source tree, and is structurally forbidden from importing `evidence.engine`.

The **Aggregation Capability Matrix** is the centrepiece: an executable registry recording which Evidence categories have a derivable denominator and which do not, with default-deny lookup. `whitelisted_api_decoration` aggregates; `controller_lifecycle_hook` does not, and says why.

**The project's first empirically calibrated figure:** `frappe.validate_and_sanitize_search_inputs` appears on 59 of 705 whitelisted symbols in ERPNext — `8.37%`. This confirmed a falsifiable prediction written into the implementation plan *before the engine existed*. Every other number in the project remains tagged `heuristic_default`.

### The `architect` CLI

Three commands, wired through the Composition Root so that **`runtime/` contains no engine import at all** — verified by AST scan and by subprocess `sys.modules` inspection after `import runtime.cli`:

```
architect evidence extract <repository> --version … --commit …
architect patterns aggregate <repository> --version …
architect patterns report <repository> --version …
```

Every command emits the same six sections in the same order, always, including the empty ones, from a single frozen `CommandOutput` that carries strings only. Both output modes render from that one object, so `--json` cannot diverge from the human render.

## Architectural Decisions Made During Implementation

- **`support`, not `confidence`.** `evaluation.contract.Confidence` already means *inferential strength*. Frequency is a different quantity and got a different name. `confidence` is reserved for Sprint 24's Verification stage.
- **A skip is a result, not a message.** `SkippedAggregation` is typed, persisted, asserted on by tests, and printed in full by the CLI. Staying silent would make "we cannot measure this" indistinguishable from "there is nothing here".
- **JSONL over a database.** The corpus is small and the artifact is a reviewable input to an argument. `sort_keys=True` makes rewrites byte-identical and reviewable under `git diff`. Enforced by a boundary test that forbids importing any dataframe or database library.
- **The Composition Root is the only door.** Extending Sprint 13's pattern one layer out: `composition_root/evidence_platform.py` is a named, disclosed consumer of both engines, and both boundary test files were updated in place to say so. No other file gained an exception.
- **The Output Contract was built first, not last.** Deferring it would have meant three commands with ad-hoc output and then rewriting all three.

## Public Interfaces

| Entry point | Returns |
|---|---|
| `evidence.extract_evidence(EvidenceExtractionRequest)` | `EvidenceSet` |
| `evidence.write_evidence_set` / `read_evidence_set` | — / `EvidenceSet` |
| `aggregation.aggregate_patterns(AggregationRequest)` | `PatternSet` |
| `aggregation.write_pattern_set` / `read_pattern_set` | — / `PatternSet` |
| `composition_root.evidence_platform` | The three CLI-facing wiring functions |

## Test Statistics

- **2,298 tests passing** repository-wide.
- **100% statement coverage** on `evidence/` and `aggregation/` (530 statements) and on all new CLI code.
- `ruff check` clean repository-wide.
- `mypy --strict` clean on every file these sprints touched.

## Validated Against Real Repositories

The full chain was re-run against the real checkouts and compared to the committed corpus:

| Check | Result |
|---|---|
| `pattern-data/*.patterns.jsonl`, both repositories | **byte-identical** to the committed artifacts |
| All 2,057 `evidence_id` values | regenerated identically |
| Every non-timestamp Evidence field, in order | identical |
| `git status` after each command | clean; writes confined to the given `--output-dir` |

## Known Limitations

1. **Closed in Sprint 22 (`v1.4.0`) — the lifecycle-hook denominator gap.** At `v1.3.0`, 237 records in `frappe` and 476 in `erpnext` were counted but not aggregated. Sprint 22 added class-definition Evidence and inheritance resolution; the measured populations are now 275 and 510 respectively. See the [Sprint 22 Release Notes](SPRINT22_RELEASE_NOTES.md).
2. **Closed in Sprint 22 (`v1.4.0`) — one measurable category.** Both behavioural categories now have a derivable population.
3. **Two repositories.** `CanonicalRepository` is a closed enum of `frappe` and `erpnext`.
4. **Cross-repository comparison is undefined**, deliberately, and has no command surface.
5. **Evidence artifacts are not byte-reproducible.** Each record carries a `collected_at` wall-clock timestamp, correctly excluded from `evidence_id`. Re-extraction therefore shows every line of `evidence-data/` as changed under `git diff` even when nothing substantive did. Pattern artifacts do not have this property. Not a defect — the determinism contract exempts timestamps — but worth a decision in a future sprint.
6. **`mypy --strict` is not green repository-wide.** 15 errors remain in two Sprint 1 test files (`tests/test_event_bus.py`, `tests/test_pipeline_engine.py`), untouched by these sprints and pre-dating them.
7. **`ruff format --check` reports 9 files.** Four hunks in `runtime/cli.py` pre-date these sprints; four were added by the CLI work. `ruff check`, the configured lint gate, passes. Left as-is deliberately: reformatting that file would also rewrite frozen Sprint 1 code.

## Follow-up Work

- **CLI supporting corpora** — expose Sprint 22's cross-repository resolution through `architect patterns aggregate --supporting …`; the API and persisted provenance already support it.
- **`hrms`** — 613 `.py` files, officially maintained by Frappe Technologies, and ranked `KS-0033` / rank #1 / P0 in this project's own [`knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md`](knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) while the engine currently rejects it. Adding it is a contract change with its own review, and it needs one question settled first: 90% adoption inside `frappe` means *this is the standard*, while 90% inside a consumer application means something different. The corpus must not blur the two.
- ~~**Sprint 23 — Candidate Rules**~~ — became an eligibility investigation instead. [RQ-0003](research/RQ-0003-evidence-derived-candidate-eligibility.md) and [ADR-0016](adr/ADR-0016-no-automated-candidate-formation.md): **no automated Candidate Formation engine was built.** Future work is selected from demonstrated backlog and research needs rather than from an assumed Pattern → Candidate → Verification sequence. `confidence` remains reserved and unused.
