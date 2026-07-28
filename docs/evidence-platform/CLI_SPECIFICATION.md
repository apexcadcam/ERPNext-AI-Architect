# EVIDENCE PLATFORM CLI — ARCHITECTURE SPECIFICATION

**Version:** 1.1
**Status:** Ratified and implemented.
**Surface:** [`runtime/cli.py`](../../runtime/cli.py), wired through [`composition_root/evidence_platform.py`](../../composition_root/evidence_platform.py)

> **Provenance of this document.** Written and approved before implementation; every section number cited in `runtime/cli.py` and `composition_root/evidence_platform.py` refers to it. Committed on 2026-07-28, after the fact. Where this document and the code disagree, **the code and its tests are authoritative**; §11 records the deltas, and there are three.

An exposure layer only. No new engine, no new analysis, no change to any existing engine's behaviour.

---

## 1. Why this exists before Sprint 22

Sprint 21 proved a principle concretely: running Pattern Aggregation revealed the lifecycle-hook denominator gap, which was **invisible** during Sprint 20 despite 100% coverage and zero defects. A consumer finds what tests cannot.

Before this, the platform had no consumer at all — every run was a throwaway script in a scratch directory. This CLI is the first real one, and its job is as much to *reveal what is missing* as to produce output.

## 2. The boundary decision this specification settles

`architect` lives in `runtime/cli.py`. But `runtime` and `composition_root` are both listed in `_FROZEN_PACKAGE_DIRS` in the `evidence` and `aggregation` boundary tests, each asserting that no frozen package imports the engine. So wiring the platform into the CLI **necessarily** changes a declared boundary.

| Option | Verdict |
|---|---|
| `runtime/cli.py` imports `evidence`/`aggregation` directly | ✗ Rejected. Makes the Runtime depend on two leaf capabilities; the CLI grows engine knowledge |
| A standalone script outside the package tree | ✗ Rejected. Not installable, not tested, not discoverable — repeats the problem this exists to fix |
| **`composition_root` wires it; `runtime/cli.py` calls `composition_root`** | ✓ **Chosen** |

This is not a new pattern. Sprint 13 created `composition_root` as *the one place allowed to import every frozen package together and wire them*; Sprint 14 made `runtime/cli.py` a named, disclosed, sanctioned consumer of it and updated the boundary test in place to say so. This specification does the same thing one layer further out.

**What does not change:** `evidence` and `aggregation` still import nothing from each other's engines, still import no Repository Intelligence package, and nothing imports *them* except the one named exception.

## 3. Commands

### 3.1 `architect evidence extract <repository>`

```
architect evidence extract erpnext --version v15.102.0 --commit 1d14ba16…
architect evidence extract frappe --version v15.103.1 --commit 61ab7e2b… --source-root /path --json
```

- `--version` / `--commit` are **required**. Extraction §2 makes provenance caller-supplied and never auto-detected, so a stored `EvidenceSet` always says which revision it describes. Inferring them from a previous run's metadata would let a fresh extraction inherit a stale label silently.
- `--source-root` defaults to `/home/gaber/frappe-bench/apps/<repository>`; `--output-dir` defaults to `evidence-data/`.
- Reports files examined/skipped/failed, evidence extracted, truncation, and the paths written.

### 3.2 `architect patterns aggregate <repository>`

```
architect patterns aggregate erpnext --version v15.102.0
architect patterns aggregate erpnext --version v15.102.0 --min-occurrences 5 --json
```

- Reads from `evidence-data/`, writes to `pattern-data/`.
- `--min-occurrences` defaults to the **registered** `MIN_OCCURRENCES_THRESHOLD`, read from the registry rather than repeated as a literal.
- Prints every `SkippedAggregation` with its reason in full — the declared gaps must be visible in the terminal, not buried in a file.

### 3.3 `architect patterns report <repository>`

```
architect patterns report erpnext --version v15.102.0
```

Read-only; runs no engine and writes nothing. Renders, in order: provenance; each category's population description; the measured Patterns in persisted order; the subjects observed below threshold; the skipped aggregations.

## 4. Out of scope

- **`compare` between repositories** — genuinely useful, but cross-repository semantics are deferred by Aggregation §4. A command that *implies* comparability before that is settled would encode a claim the platform cannot support.
- Any command touching Repository Intelligence.
- Extending `CanonicalRepository` — a contract change with its own review, not something smuggled in through a CLI.
- Any LLM call, any new dependency, any change to an engine's behaviour.

## 5. Composition Root additions

Thin functions that wire existing pieces and own no logic — an engine entry point plus the matching persistence call, nothing more:

```python
extract_repository_evidence(...)  -> EvidenceSet
aggregate_repository_patterns(...) -> PatternSet
read_repository_patterns(...)      -> PatternSet
```

Tested by AST assertion that these functions contain no branching, looping, or arithmetic, and call nothing but engine and persistence entry points.

## 6. Output Contract

**Every command emits the same six sections, in the same order, always — including the empty ones.**

```python
class CommandOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: tuple[tuple[str, str], ...]   # ordered label/value pairs
    artifacts_written: tuple[str, ...]
    warnings: tuple[str, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...]
    exit_code: int
```

It carries **strings only** — no engine types — so it has zero dependency on `evidence` or `aggregation` and lives in `runtime/` without touching any boundary. Both output modes are rendered from the one object, which turns "`--json` never diverges from the human render" from a convention someone must remember into a property of the type.

Empty sections render as `(none)` rather than being omitted, so "absent" and "empty" are never confusable.

Two consequences, which are the point rather than side effects:

- **`SKIPPED` is a first-class section.** It is where `SkippedAggregation` surfaces, keeping declared gaps visible at the terminal — matching the decision that made them a persisted result rather than a log line.
- **A failing command still emits all six sections.** An error populates `ERRORS` and sets `exit_code`; it does not replace the output with a bare message, so tooling parses success and failure identically.

Duplicate summary labels are rejected at construction: `render_json` keys the summary by label, so a duplicate would render twice for a human and collapse to one key in JSON — exactly the divergence between modes this contract prevents.

## 7. Failure handling

- A missing source root or missing artifact exits `1` with the engine's own message — never a stack trace.
- The CLI catches `EvidenceError_` and `AggregationError_` only, obtained as data from the Composition Root rather than by importing the engines' error modules.
- `--json` emits on the same code path as the human render.

## 8. Testing

Command-level tests via `typer.testing.CliRunner`, against real engines and real artifacts on disk — the commands are thin adapters, so mocking the layer beneath would leave nothing under test. Output Contract conformance is asserted per command, in both modes, including on the failure path. 100% coverage on new code.

## 9. Implementation sequence

| Commit | Content |
|---|---|
| 1 | `CommandOutput` contract + renderer |
| 2 | Composition Root additions |
| 3 | `architect evidence extract` |
| 4 | `architect patterns aggregate` |
| 5 | `architect patterns report` |
| 6 | Release validation |

The Output Contract is sequenced **first**, so each command is written against it. Deferring it would mean three commands with ad-hoc output and then rewriting all three.

## 10. Deliverable

A person who has never seen this codebase can analyse a repository and read the result without writing Python.

## 11. Known deltas between this document and the code

Three, all decided during implementation and all in the direction of §2's boundary rule:

1. **`extract_repository_evidence` takes primitives, not an `EvidenceExtractionRequest`.** §5 specified a request-shaped parameter, but building that request obliges the caller to import `evidence.contract` — and `runtime/cli.py` is precisely the caller. The request is constructed inside the Composition Root instead, so the CLI holds no engine import at all.
2. **Three Composition Root functions where §5 specified two.** `patterns report` is read-only, but §2 says the CLI reaches the platform *only* through the Composition Root; without `read_repository_patterns` the report command would have to import `aggregation.persistence` directly, which is the coupling §2 rejected.
3. **`patterns report` catches one exception type where its siblings catch two.** `extract` and `aggregate` build a pydantic request, so a `ValidationError` can escape them. `report` builds nothing, and `read_pattern_set` converts every `ValueError` into `AggregationError_` before returning — a second clause would be unreachable code kept for symmetry.

Two constants (`CANONICAL_REPOSITORY_NAMES`, `EVIDENCE_PLATFORM_ERRORS`) and one default (`DEFAULT_MIN_OCCURRENCES`) are exposed from the Composition Root as plain data for the same reason as delta 1: the CLI needs to name valid repositories, catch engine errors, and default a threshold without importing an engine to do it.
