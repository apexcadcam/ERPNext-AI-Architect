# Evidence Platform — Open Work Items

Opened at the `v1.3.0` release. Each item states what is wrong or missing, why it matters, and what "done" means, so it can be picked up without re-deriving the context.

Ordered by dependency, not by size: **W5 unblocks the platform's central limitation**, and **W3 depends on a question W3 itself has to answer first.**

| ID | Item | Kind | Blocking? |
|---|---|---|---|
| [W1](#w1--repository-wide-typing-cleanup) | Repository-wide typing cleanup | Debt, pre-existing | No |
| [W2](#w2--repository-wide-formatting-normalization) | Repository-wide formatting normalization | Debt, optional | No |
| [W3](#w3--hrms-support) | HRMS support | Contract change | No — needs a decision first |
| [W4](#w4--timestamp-reproducibility-decision) | Timestamp reproducibility decision | Design decision | No |
| [W5](#w5--sprint-22-denominator-work) | Sprint 22 — denominator work | Feature | ✅ **Done** — closed by Sprint 22 |
| [W6](#w6--a-diagnostic-statistic-for-filtered-occurrences) | Diagnostic statistic for filtered occurrences | Consideration | No |

The release validation report numbered three of these as findings; the mapping, so the two vocabularies do not drift apart: **F1 → W4** (timestamps), **F2 → W1** (typing), **F3 → W2** (formatting). `W` identifiers are the ones to use from here.

---

## W1 — Repository-wide typing cleanup

**Kind:** Technical debt · **Origin:** pre-existing, Sprint 1 · **Priority:** medium

`mypy --strict .` reports **15 errors in 2 files**:

- `tests/test_event_bus.py` — 5 errors
- `tests/test_pipeline_engine.py` — 10 errors

Both files are byte-identical to their state at `9ff396d` and were never touched by Sprints 20, 21 or the CLI work. Every file those sprints did touch passes `mypy --strict` cleanly.

Most errors are missing annotations, but **two are genuine signature mismatches**, not cosmetic:

```
Argument 2 to "subscribe" of "EventBus" has incompatible type
  "Callable[[Event], bool]"; expected "Callable[[Event], None]"
```

A subscriber returning `bool` where the contract says `None` is worth understanding before it is annotated away — the test may be encoding a real expectation the `EventBus` contract does not support.

**Done when:** `mypy --strict .` exits clean across all 408 files, and the two `Callable` mismatches are resolved by a deliberate decision (fix the test, or widen the contract) rather than by a cast.

**Caution:** both files test frozen Sprint 1 code. Changing the `EventBus` contract is out of scope for a typing cleanup; if the contract turns out to be wrong, that is its own item.

---

## W2 — Repository-wide formatting normalization

**Kind:** Technical debt · **Origin:** mixed · **Priority:** low, explicitly optional

`ruff format --check .` reports **9 files**. `ruff check` — the lint gate the project actually configures under `[tool.ruff.lint]` — passes repository-wide.

| Origin | Files |
|---|---|
| Sprint 1 era | `runtime/config/loader.py`, `runtime/events/bus.py`, `runtime/pipeline/engine.py`, `runtime/registry/plugin_registry.py`, `tests/test_cli.py`, `tests/test_event_bus.py`, `tests/test_pipeline_engine.py`, `tests/test_plugin_registry.py` |
| Mixed | `runtime/cli.py` — 4 hunks pre-date the CLI work, 4 were added by it |

The four new hunks are option declarations exceeding the 110-character line limit that the formatter would wrap. All 7 files the CLI sprint created are format-clean.

**Why it was left:** running the formatter on `runtime/cli.py` also rewrites the 4 pre-existing hunks in frozen Sprint 1 code, so it is not a neutral cleanup.

**Done when:** either `ruff format .` is run repository-wide in a single isolated commit that touches no logic, **or** a decision is recorded that `ruff format` is not a gate for this project and only `ruff check` is. Either resolution is acceptable; the current in-between state is the only unsatisfactory one.

---

## W3 — HRMS support

**Kind:** Contract change · **Priority:** high value, blocked on a design question

`CanonicalRepository` is a closed enum of `frappe` and `erpnext`. `hrms` is rejected at four points, all derived from that one enum — so the code change itself is small.

**Why it matters:** `hrms` is 613 `.py` files, officially maintained by Frappe Technologies, and ranked **`KS-0033`, rank #1, priority P0, trust 93** in this project's own [`KNOWLEDGE_SOURCE_CATALOG.md`](../../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md), which calls first-party Frappe products *"more valuable than any blog, forum thread, or third-party tutorial in this catalog."* The committed catalogue ranks it first while the engine refuses it. That contradiction is currently recorded nowhere but here.

**The exclusion was never a considered decision.** No code, comment, or test in either engine mentions `hrms`. The docstring justifying the closed enum argues against *other frameworks* — "Django, Odoo, …" — which does not cover a first-party Frappe application. It is an implementation shortcut, not an architectural invariant.

### The question that must be answered first

**Framework versus consumer.** 90% adoption of a pattern inside `frappe` means *this is the standard*. 90% adoption inside a consumer application means *this application does it this way* — possibly a repeated mistake. Both currently produce a `Pattern` of identical shape.

Adding `hrms` without settling this blurs "the framework defines this" with "one app happens to do this", and the corpus cannot be un-blurred afterwards.

**Likely shape of the answer:** a `repository_role` (framework / first-party application / third-party application) recorded on the Evidence or the Pattern, so support figures stay separable by role. That is a contract change with its own review, not an enum edit.

**Done when:** the role distinction is designed and approved; `CanonicalRepository` gains its new member(s); `tests/evidence/test_contract.py::test_canonical_repository_defines_exactly_the_two_documented_values` is updated deliberately; and `hrms` is extracted, aggregated, and its artifacts committed alongside the existing corpus.

**Explicitly not in scope:** the user's own applications (`apex_dashboard`, `apex_maintenance`, `apex_crm`, `crm_apex`, `apex_commission`, `apex_customization`, `apex_item`, `commission_manager`, …). They are personal-effort applications and are not a standard; treating them as corpus would poison exactly the distinction this item exists to protect.

---

## W4 — Timestamp reproducibility decision

**Kind:** Design decision · **Priority:** medium

Re-extraction reproduces **every `evidence_id` and every non-timestamp field identically and in identical order** — 812 records for `frappe`, 1,245 for `erpnext`. But the persisted JSONL is **not byte-identical**, because each record carries a `collected_at` wall-clock timestamp.

This is consistent with the determinism contract, which exempts timestamps, and `collected_at` is correctly excluded from the content-addressed `evidence_id`. **It is not a defect.**

**Why it still needs a decision:** JSONL with `sort_keys=True` was chosen over a database specifically so artifacts would be reviewable under `git diff`. A re-extraction currently shows all 2,057 lines as changed when nothing substantive did, which defeats that purpose for the artifact it was chosen for. `pattern-data/` does not have this problem — `Pattern` records carry no per-record timestamp and reproduce byte-for-byte.

**Options, none yet chosen:**

1. Move `collected_at` from each record to the `EvidenceSet` metadata sidecar — one timestamp per run instead of 2,057. Preserves the information, restores byte-level reproducibility of the JSONL.
2. Drop `collected_at` entirely. The sidecar already records `extracted_at`; per-record collection time has no consumer today.
3. Keep it and accept the churn, recording the decision so it stops being re-discovered.

Option 1 looks strongest, but it changes the Evidence schema and would require re-extracting and re-committing the corpus.

**Done when:** one option is chosen and recorded in the Evidence Extraction specification, and — if the schema changes — `schema_version` is incremented and the corpus regenerated.

---

## W5 — Sprint 22: denominator work

**Kind:** Feature · **Status: ✅ closed by Sprint 22** · originally: highest priority, blocking the second Evidence category

**Outcome.** The population is measured: **275** (frappe) and **510**
(erpnext, with frappe supplied as resolution context). `validate` is
implemented by 31.6% of frappe controllers and 35.3% of ERPNext
controllers. `categories_skipped` is `0`; the `SKIPPED` section is empty
because the denominator now exists, not because a row was removed.

What follows is the item as originally written.

The platform's central declared limitation. **237 Evidence records in `frappe` and 476 in `erpnext` are collected but cannot be aggregated**, because the population is not derivable from Evidence alone: the collector emits a record only where a hook is *found*, so classes without hooks leave no trace. The numerator exists; the denominator does not.

The engine refuses to divide anyway, and records a persisted `SkippedAggregation` whose reason names this work explicitly.

**Measured, not assumed.** Against real ERPNext v15.102.0 the true population is **at least 482** — 448 direct `class X(Document)` plus at least 34 via intermediate bases (`AccountsController`, `TransactionBase`, `StockController`, `BuyingController`, `SellingController`). Multi-level inheritance chains remain unresolved even by that count, which is why the figure is a lower bound rather than an answer.

**What is required:** a new Evidence category recording **class definitions and their base classes**, so the set of `Document` subclasses becomes derivable from persisted Evidence — including through intermediate bases, which means resolving inheritance chains rather than matching a single base name.

**Done when:**

- The new category emits atomic Evidence for class definitions with their bases.
- A resolver derives the `Document`-subclass population, transitively.
- `POPULATION_BASES` moves `CONTROLLER_LIFECYCLE_HOOK` from `skipped_no_population` to `aggregated`.
- `architect patterns aggregate` produces real lifecycle-hook Patterns, and the `SKIPPED` section for that category disappears **because it was earned, not suppressed**.
- The corpus is regenerated and committed.

**Watch for:** the resolved population must count classes, not records, and must not silently include classes from a different repository in the same run.

### The check to run afterwards, and how to frame it

Re-run the full chain and compare against the `v1.3.0` corpus — but **the comparison that matters is a regression check, not an impact measurement.**

There is nothing to compare for lifecycle hooks: today they are not measured at all, so "before" is empty and any "after" is new information rather than a delta. What *is* comparable is the category that already works:

| Quantity | Expected after Sprint 22 |
|---|---|
| `whitelisted_api_decoration` occurrences, population, support | **Identical** — 518/520 and 15/520 for `frappe`, 705/705 and 59/705 for `erpnext` |
| Every existing `pattern_id` | **Identical** — the hash covers repository, version, commit, category, subject, none of which change |
| `categories_present` | 2 → 3 |
| `categories_skipped` | 1 → 0 |
| Existing `evidence_id` values | **Identical** — new records are added; none of the old ones move |

Any drift in row one or two means the new collector perturbed the existing category, which would be a defect in the new work rather than a finding about the corpus. That is the real value of re-running: adding a third Evidence category must be **purely additive** to the two that exist.

---

## W6 — A diagnostic statistic for filtered occurrences

**Kind:** Consideration, not yet a decision · **Priority:** low · **Raised by:** Sprint 22, Commit 7

Commit 7 established the membership invariant: an occurrence counts only when its subject entity belongs to the population defining the support ([Aggregation §5.1](PATTERN_AGGREGATION_SPECIFICATION.md)). `OCCURRENCE_FILTERS` enforces it before grouping.

**The observation.** That filtering is currently **invisible in the artifact.** A reader of frappe's `validate 84/275` cannot tell that three hook records were set aside, or why. The number is correct; the fact that a narrowing occurred is simply not recorded.

**Why this is a consideration and not a defect.** Exclusion here is not a gap — it is the measurement being correct. `EMail.validate` is not a lifecycle hook, so leaving it out is not "something we could not measure". That is why it produces no `SkippedAggregation`: [D7](../DECISION_LOG.md) reserves that for what the platform can see and cannot honestly measure, and diluting it with correct exclusions would weaken the signal it exists to carry.

**But the platform's own habit argues for visibility.** Every other narrowing this system performs is recorded — `observed_below_threshold` keeps subjects that did not reach the threshold, `unresolved_bases_count` keeps the residue. A filtered occurrence is the one narrowing that leaves no trace.

**Shape it might take**, none chosen:

1. A statistic — `occurrences_filtered: int` on `AggregationStatistics`, counting records excluded by an occurrence filter.
2. Per-category detail, so a reader can see *which* category narrowed and by how much.
3. Nothing, with a recorded decision that a correct exclusion needs no artifact trace.

**Cost:** options 1 and 2 are contract changes, so they move `schema_version` and require regenerating the corpus. That is why Commit 7 deliberately did not take them.

**Done when:** one option is chosen and recorded — including option 3, which is a legitimate answer.
