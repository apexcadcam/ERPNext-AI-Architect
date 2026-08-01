# Evidence Platform — Open Work Items

Opened at the `v1.3.0` release. Each item states what is wrong or missing, why it matters, and what "done" means, so it can be picked up without re-deriving the context.

Ordered by dependency, not by size. Two items are now closed: **W5** measured the lifecycle-hook denominator, and **W3** — which depended on a question it had to answer first — was closed once [ADR-0016](../../adr/ADR-0016-no-automated-candidate-formation.md) dissolved that question and [RQ-0004](../../research/RQ-0004-hrms-as-a-measurable-repository.md) replaced it with a measured one.

| ID | Item | Kind | Blocking? |
|---|---|---|---|
| [W1](#w1--repository-wide-typing-cleanup) | Repository-wide typing cleanup | Debt, pre-existing | No |
| [W2](#w2--repository-wide-formatting-normalization) | Repository-wide formatting normalization | Debt | Partially closed — 8 files remain |
| [W3](#w3--hrms-support) | HRMS support | Contract change | ✅ **Done** — closed by Sprint 24 |
| [W4](#w4--timestamp-reproducibility-decision) | Timestamp reproducibility decision | Design decision | No |
| [W5](#w5--sprint-22-denominator-work) | Sprint 22 — denominator work | Feature | ✅ **Done** — closed by Sprint 22 |
| [W6](#w6--a-diagnostic-statistic-for-filtered-occurrences) | Diagnostic statistic for filtered occurrences | Consideration | No |
| [W7](#w7--durable-evidenceset-identity) | Durable `EvidenceSet` identity / locator | Research follow-up | **No** |
| [W8](#w8--explicit-zero-observations-for-absent-subjects) | Explicit zero-observations for absent subjects | Research follow-up | **No** |
| [W9](#w9--adr-documentation-provenance) | ADR documentation provenance and numbering | Repository hygiene | **No** |
| [W10](#w10--version-string-format-consistency) | Version-string format consistency | Observation | **No** |

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

**Kind:** Technical debt · **Origin:** mixed · **Priority:** low · **Status: partially closed, not as planned**

### What the plan was, and what actually happened

This item said the formatter should be run *"in a single isolated commit that touches no logic"*, precisely so that reformatting frozen Sprint 1 code would be a visible, deliberate act.

**That is not what happened.** `runtime/cli.py` was normalized by `ruff format` inside [`d6d7a96`](../DECISION_LOG.md) — the Sprint 22 Commit 7 fix — as a side effect of formatting the file after editing it. The commit message does not mention it. The isolated formatting commit this item planned therefore never occurred, and this entry is corrected to describe the repository as it is rather than as the plan assumed.

### Verified consequences

Four of the eight reformatted hunks in `runtime/cli.py` fall in **frozen Sprint 1 code** — the option declarations, `doctor`, `plugins_list`, and `config_validate`.

**No behaviour changed.** Confirmed by comparing the parsed AST of every Sprint 1 function against its state at `189090a`: `doctor`, `plugins_list`, `config_validate`, `runtime_info`, `run_goal`, `_build_runtime` and `_emit` are all **AST-identical**. The only function added is `_resolve_supporting_corpora`, which is Sprint 22's own `--supporting` resolution.

The formatting is **kept**, by decision. It is not reverted and git history is not rewritten.

### Current state

`ruff format --check .` reports **8 files**, down from 9. `ruff check` — the lint gate the project actually configures under `[tool.ruff.lint]` — passes repository-wide.

| Origin | Files |
|---|---|
| Sprint 1 era, still unformatted | `runtime/config/loader.py`, `runtime/events/bus.py`, `runtime/pipeline/engine.py`, `runtime/registry/plugin_registry.py`, `tests/test_cli.py`, `tests/test_event_bus.py`, `tests/test_pipeline_engine.py`, `tests/test_plugin_registry.py` |
| **Normalized in `d6d7a96`** | `runtime/cli.py` — no longer in the list |

### What remains

Eight Sprint 1 files, all untouched by any sprint since. The original two resolutions still stand for them: run `ruff format` on those eight in an isolated commit, **or** record a decision that `ruff format` is not a gate for this project and only `ruff check` is.

**The lesson this item now also carries:** an incidental `ruff format` on an edited file silently normalizes whatever else is in that file. If the isolated-commit discipline matters, the formatter should be run with an explicit file list, not on a directory after an edit.

---

## W3 — HRMS support

**Kind:** Contract change · **Priority:** high value · **Status: ✅ CLOSED — implemented in Sprint 24**

### What was delivered, and what it does *not* mean

**HRMS is an explicitly admitted canonical measured repository whose required supporting-corpus closure is `{erpnext, frappe}`.** That sentence is the whole claim, and its precision matters more than its brevity.

It does **not** mean any of the following, and none of them became true:

- arbitrary Frappe applications are supported — admission stays default-deny, and each new repository costs a research question ([ADR-0017](../../adr/ADR-0017-canonical-repository-admission.md) §9);
- dependencies are discovered automatically — the closure was measured, not inferred from `required_apps` or an import graph;
- `frappe` and `erpnext` are injected for you — a caller who omits them is refused and told what to add;
- supporting corpora contribute occurrences — zero supporting records entered any HRMS numerator;
- supporting corpora join the measured population — zero supporting classes entered it;
- HRMS is a standard or a source of recommendations by virtue of being admitted. Admission says a measurement is well-defined and reproducible. It says nothing normative ([ADR-0016](../../adr/ADR-0016-no-automated-candidate-formation.md)).

### How it got here — five stages, none of them skippable

This item was open from `v1.3.0` and was never simply a matter of editing an enum. The sequence is worth keeping, because each stage changed what the next one could be:

1. **Originally blocked on framework-versus-consumer.** The item assumed that measuring a consumer application alongside the framework would blur "the framework defines this" with "one app happens to do this", and that a `repository_role` field would be needed to keep them apart.
2. **[ADR-0016](../../adr/ADR-0016-no-automated-candidate-formation.md) dissolved the assumption underneath that blocker.** It established that the platform makes no normative claims at all: support is descriptive frequency and eligibility is claim-relative. `validate` reads `84/275` in frappe, `180/510` in erpnext and `66/153` in HRMS — identically constructed measurements that only a human-authored claim could confuse. The question was not answered; it stopped being the producer's question. **`repository_role` was therefore never built**, because RQ-0004 found no *measurement* that needed it.
3. **[RQ-0004](../../research/RQ-0004-hrms-as-a-measurable-repository.md) measured HRMS and found a different, real requirement.** 613 Python files parsed, 0 parse failures, 976 records — and a lifecycle population of 143, 145, 150 or 153 depending purely on which corpora were supplied. The three incomplete configurations do not fail; they publish a smaller plausible denominator and silently drop 6, then 4, then 2 real controllers from the numerator. One class settles why both corpora are needed at once: `EmployeeMaster@hrms → Employee@erpnext → NestedSet@frappe → Document`.
4. **[ADR-0017](../../adr/ADR-0017-canonical-repository-admission.md) defined canonical repository admission.** Extractable ≠ researched ≠ safely measurable ≠ admitted. A repository's supporting-corpus closure is established by research, recorded declaratively, and enforced — not documented, because the failure is silent.
5. **Sprint 24 implemented it in four reviewed steps**, in an order chosen so no intermediate commit could publish a wrong number:
   - *policy enforcement first* — a declarative admission registry and a generic precondition at the aggregation entry point, carrying only the closures that already existed (`frappe → {}`, `erpnext → {frappe}`). Aggregating `erpnext` without `frappe` became a refusal rather than a 492-controller population;
   - *admission* — `CanonicalRepository.HRMS` and its `{erpnext, frappe}` closure entry, added in one commit so no state ever existed where HRMS was admitted without a closure;
   - *canonical provenance ordering* — a defect found before publication rather than after: persisted `supporting_corpora` preserved caller order, so the first two-corpus artifact would have depended on CLI flag order. Now sorted by `(repository, version, commit)`;
   - *publication* — artifact schema `2.0 → 3.0`, all three corpora regenerated under the current producer, and the first committed HRMS Evidence and Pattern artifacts.

### Measured outcome

| | Value |
|---|---|
| Source | `hrms` `15.51.0` at `031e97ba05ea9ba3250278450c58be01b7774f6a` |
| Evidence | 613 Python files parsed · 0 parse failures · 976 records |
| Lifecycle population | **153** · `validate 66/153` · `unresolved_bases_count 0` |
| Whitelist | population **198** · `frappe.whitelist 198/198` |
| Provenance | `multi_corpus`, supporting `erpnext v15.102.0` + `frappe v15.103.1` |
| Artifacts | `evidence-data/hrms-15.51.0.*`, `pattern-data/hrms-15.51.0.*`, schema `3.0` |

Every figure reproduces RQ-0004 exactly. `frappe` and `erpnext` measurements are unchanged — 275 and 510, `validate 84/275` and `180/510` — and their Pattern files are byte-identical to their predecessors.

**Done, verified:** `CanonicalRepository` gained its member; the conformance test formerly named `test_canonical_repository_defines_exactly_the_two_documented_values` was renamed and updated deliberately; `hrms` is extracted, aggregated and committed alongside the existing corpus; and permanent committed-corpus regression tests now protect all three sets of published figures.

**Version-string note:** the artifact is `hrms-15.51.0.*`, with no `v` prefix, because `hrms/__init__.py` declares it that way and `version` participates in artifact identity. The inconsistency with the other two corpora is deliberate and remains [W10](#w10--version-string-format-consistency).

What follows is the item as originally written, preserved unchanged. **Its framing was superseded at stage 2 above** — in particular, the `repository_role` proposal was never adopted.

---

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
implemented by **30.5%** of frappe controllers (`84/275`) and **35.3%** of
ERPNext controllers (`180/510`). `categories_skipped` is `0`; the
`SKIPPED` section is empty because the denominator now exists, not
because a row was removed.

The frappe figure was reported as 31.6% at `v1.4.0` and corrected in
Commit 7, which restricted the numerator to members of the population it
is measured against — see [W6](#w6--a-diagnostic-statistic-for-filtered-occurrences)
and [D18](../DECISION_LOG.md).

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

---

## W7 — Durable `EvidenceSet` identity

**Kind:** Research follow-up · **Priority:** low · **Blocking: no** · **Raised by:** [RQ-0003 F7](../../research/RQ-0003-evidence-derived-candidate-eligibility.md)

`PatternSet.source_evidence_set_id` is a **per-run UUID**, not a durable locator. Given only a `PatternSet`, nothing states which file or hash to open in order to resolve its `supporting_evidence_ids`.

**Why it is not blocking.** RQ-0003 traced three Patterns end to end and every `supporting_evidence_id` resolved. `repository + version + commit` already identifies the corpus uniquely, and the conventional path `evidence-data/<repository>-<version>.evidence.jsonl` locates it. The UUID is redundant rather than load-bearing.

**When it would become urgent.** If an artifact citing a Pattern ever travels outside this repository, or outlives its corpus. Neither is true today — and [ADR-0016](../../adr/ADR-0016-no-automated-candidate-formation.md) means no such artifact is being generated.

**Open shapes**, none chosen: content-address the `EvidenceSet` by digest; record a relative artifact path on the `PatternSet`; or record a decision that `repository + version + commit` plus convention is the identity, and drop the UUID's implied role.

**Done when:** one shape is chosen and recorded — including the third, which is a legitimate answer.

---

## W8 — Explicit zero-observations for absent subjects

**Kind:** Research follow-up · **Priority:** low · **Blocking: no** · **Raised by:** [RQ-0003 F6](../../research/RQ-0003-evidence-derived-candidate-eligibility.md)

Of the 11 recognised lifecycle-hook names, **four appear nowhere in frappe's artifact** — `before_submit`, `on_cancel`, `on_submit`, `on_update_after_submit`. There is no Pattern, no below-threshold entry, and no marker of any kind.

`observed_below_threshold` is **not** a zero-observation: every entry records a real count that fell below the floor. Nothing in the artifact represents zero.

**The standing rule, which this item does not relax:** absence is unusable as evidence, and **silence must never be interpreted as zero**. A naive reader could conclude from frappe's four missing names that submit hooks are discouraged in framework code; the real reason is that `frappe` core has few submittable DocTypes — a domain fact, not a practice signal.

**Why it is not blocking.** No eligible claim in RQ-0003 depends on absence. Representing zeros would be a contract change solving a problem no current candidate has.

**Open question:** should an aggregation emit an explicit zero for every recognised subject in a category's closed vocabulary that was observed zero times — and if so, is a zero meaningfully different from an absence when the vocabulary itself may be incomplete?

**Done when:** either explicit zero-observations are designed and approved, or a decision is recorded that negative evidence stays permanently out of scope for this platform.

---

## W9 — ADR documentation provenance

**Kind:** Repository hygiene / documentation provenance · **Priority:** low · **Blocking: no** · **Raised by:** establishing the next ADR number during Sprint 23

Two observations, found while determining that `ADR-0016` was free. **Neither is a Sprint 23 functional blocker**, and neither was fixed.

### 1. Referenced ADRs with no file

`ADR-0003` through `ADR-0013` are referenced across sprint release notes, architecture packages, and at least one source docstring (`runtime/cli.py` cites `ADR-005`), but no corresponding files exist in [`adr/`](../../adr/). The directory holds six ADRs; the references imply roughly seventeen.

A reader following any of those references today finds nothing.

### 2. Two numbering conventions coexist

`ADR-001-analysis-knowledge-direction.md` uses three digits; every other file uses four (`ADR-0001`, `ADR-0002`, `ADR-0009`, `ADR-0014`, `ADR-0015`, `ADR-0016`). Both are referenced in prose, sometimes in the same document.

### Constraints on any future work here

- **Reconstruct what historically existed first.** The sprint release notes describe "ADR Candidates A/B/C" that were approved during sprint reviews and may never have been written as files. Establishing what was actually decided comes before anything else.
- **Do not create replacement ADRs from inference merely to fill numbering gaps.** An invented ADR is worse than a dangling reference: it looks authoritative and records a decision nobody made.
- **Do not renumber existing ADRs** as part of that investigation. `adr/README.md` states an ADR is *"kept permanently as-is → superseded by a new ADR if the decision is later reversed (never edited in place)"*, and renumbering would break every existing citation. If unification is wanted, it needs its own architectural decision.

**Done when:** the historical record is established and a decision is recorded — including "the gaps are permanent and the references are to sprint-review decisions rather than to files", which is a legitimate outcome.

---

## W10 — Version-string format consistency

**Kind:** Observation · **Priority:** low · **Blocking: no** · **Raised by:** [RQ-0004](../../research/RQ-0004-hrms-as-a-measurable-repository.md)

The committed corpora use a leading `v` — `frappe-v15.103.1`, `erpnext-v15.102.0` — while HRMS declares `__version__ = "15.51.0"` without one. Since Sprint 24 this is no longer hypothetical: `hrms-15.51.0.evidence.jsonl` and `hrms-15.51.0.patterns.jsonl` sit committed beside them.

**No contract constrains the format.** `version` is `Field(min_length=1)` on `Source`, `Evidence`, `EvidenceSet`, `Pattern`, `PatternSet` and `CorpusRef` — checked across both contract modules. Nothing normalises, validates or parses it.

**Why it is not blocking, and was deliberately kept out of HRMS support:** `version` participates in `evidence_id` and `pattern_id` hashing and in artifact filenames. **Silently normalising it would change artifact identity** — the same class of act ADR-0015 and the Sprint 22 review refused elsewhere. It is cosmetic today and only becomes a hazard for tooling that later splits artifact filenames on `-`.

**Open question:** should `version` be recorded exactly as the upstream repository declares it — which is the current, faithful behaviour — or normalised to one house format? The first is more honest about provenance; the second is friendlier to parsing. Either is defensible; the current mixture is what is not.

**Done when:** one is chosen and recorded, including "record upstream verbatim and never parse filenames", which is a legitimate answer.
