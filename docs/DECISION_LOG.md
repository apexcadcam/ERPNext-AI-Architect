# DECISION LOG

Why the Evidence Platform is shaped the way it is.

The specifications say *what* the platform does. This file says *why* — the decision, the alternative that was rejected, and what made the difference. It exists because the reasoning behind a design is the first thing lost, and the first thing a future maintainer needs before changing anything.

**Scope:** Sprints 20–22 and the CLI, `v1.1.0` → Sprint 22. One entry per decision that would be expensive to reverse or easy to undo by accident.

**How to read an entry:** the *Instead of* line is the option a reasonable engineer would have picked. If you are about to change something here, that line is usually what you are about to reintroduce.

---

## D1 — Evidence is atomic: one record per observed fact

**Decided:** Sprint 20 · **Lives in:** [`evidence/collectors.py`](../evidence/collectors.py) · **Spec:** [Extraction §5](evidence-platform/EVIDENCE_EXTRACTION_SPECIFICATION.md)

A function carrying three decorators produces three Evidence records, never one record with a composite subject.

**Instead of:** bundling a symbol's decorators into one record, which is the obvious compression.

**Why it mattered later:** because subjects were never bundled, counting *distinct symbols* is a set operation rather than a parse. Every population in the platform depends on that, and Sprint 21 got it for free. A compression decision in Sprint 20 decided whether Sprint 21 was cheap or impossible.

---

## D2 — `evidence_id` is content-addressed, `evidence_set_id` is not

**Decided:** Sprint 20 · **Lives in:** `_compute_evidence_id`

`evidence_id` is a `sha256` over the fact itself. `evidence_set_id` is a fresh UUID per run.

**Instead of:** a UUID for both, which is the default for anything called an id.

**Why:** they answer different questions — identity of *the observation* versus identity of *the act of observing*. The split is what lets a re-extraction be compared to its predecessor at all: 2,057 ids regenerated identically across Sprint 22's corpus change, which is how "purely additive" was verified rather than asserted.

---

## D3 — A parse failure is a result, not an exception

**Decided:** Sprint 20 · **Lives in:** `EvidenceExtractionError` inside `EvidenceSet`

One unparseable file becomes a record in the returned artifact. Extraction still completes.

**Instead of:** raising, or logging and continuing.

**Why:** a log line is not evidence. A persisted error record can be asserted on, counted, and reviewed. Both real trees currently report zero — which is only meaningful *because* a non-zero value would have been visible.

---

## D4 — JSONL with `sort_keys=True`, not a database

**Decided:** Sprint 20 · **Enforced by:** a boundary test forbidding pandas, numpy, duckdb, sqlite3, sqlalchemy

**Instead of:** SQLite or DuckDB, which would handle far more data far more efficiently.

**Why:** the corpus is small, and the artifact is a reviewable input to an argument, not a query workload. A database would make the evidence harder to inspect than the code it describes.

**Known cost:** re-extraction is not byte-identical, because each record carries a `collected_at` timestamp — so `git diff` shows every line changed when nothing substantive did. This partly defeats the reason JSONL was chosen. Open as [W4](evidence-platform/BACKLOG.md#w4--timestamp-reproducibility-decision).

---

## D5 — `support`, never `confidence`

**Decided:** Sprint 21 · **Enforced by:** a test asserting no field named `confidence` exists

**Instead of:** `confidence`, the word everyone reaches for.

**Why:** `evaluation.contract.Confidence` already existed, meaning *how strongly cited evidence supports a conclusion* — a judgement about inferential strength. Frequency across a population is a different quantity. Reusing the word would have made two incomparable things look comparable in every future report. `confidence` is reserved for Sprint 24's verification stage.

---

## D6 — No population, no Pattern

**Decided:** Sprint 21 · **Enforced by:** `Pattern.population` constrained `ge=1`

**Instead of:** publishing a count when the denominator is unknown.

**Why:** a Pattern without a denominator is a count wearing the costume of a rate. The constraint makes a zero denominator *unrepresentable*, so it cannot be produced even by a future bug in a resolver.

---

## D7 — A skip is a first-class result

**Decided:** Sprint 21 · **Lives in:** `SkippedAggregation`, persisted and test-asserted

When the platform can see a signal but cannot honestly measure it, that becomes a typed field in the artifact carrying the full reason.

**Instead of:** omitting the category, or logging a warning.

**Why:** a silently absent category is indistinguishable from a category with nothing to report, and only one of those is correct. Making it a persisted, asserted field means the gap **cannot drift closed unnoticed** — which is exactly what happened: Sprint 22 had to earn its removal, and a test would have failed if the row were simply deleted.

**This is the decision the platform's credibility rests on.** It was declared for two releases and then closed by measurement, not by quietly dropping it.

---

## D8 — The denominator gap was found by measurement, not assumption

**Decided:** Sprint 21 · **Recorded in:** the `POPULATION_BASES` blocker text, printed by every run

Running the engine on the real corpus revealed that the lifecycle-hook population was not derivable — invisible during Sprint 20 despite 100% coverage and zero defects.

**Why it is here:** it is the evidence for a general claim this project makes — *a consumer finds what tests cannot*. It is also why the CLI was built before Sprint 22 rather than after.

---

## D9 — The CLI reaches the engines only through the Composition Root

**Decided:** CLI sprint · **Spec:** [CLI §2](evidence-platform/CLI_SPECIFICATION.md) · **Verified by:** AST scan plus `sys.modules` inspection

`runtime/` contains **no engine import at all**. Valid repository names, engine error types, and the default threshold reach the CLI as plain data from `composition_root/evidence_platform.py`.

**Instead of:** importing `evidence` and `aggregation` in `runtime/cli.py`, which is two lines and obviously simpler.

**Why:** it would make the Runtime depend on two leaf capabilities and let the CLI accumulate engine knowledge. The exception is confined to one named file and disclosed in both boundary test files — the same shape Sprint 14 used.

---

## D10 — One frozen `CommandOutput`, six sections, always

**Decided:** CLI sprint, **built first** · **Lives in:** [`runtime/output.py`](../runtime/output.py)

Every command emits `SUMMARY`, `ARTIFACTS WRITTEN`, `WARNINGS`, `SKIPPED`, `ERRORS` and an exit code — including the empty ones, rendered `(none)`.

**Instead of:** building it last, which is what was originally proposed.

**Why the order mattered:** deferring it would have meant three commands with ad-hoc output and then rewriting all three. Building it first made each command cost nothing extra.

**What it buys:** both output modes render from one object, so `--json` *cannot* diverge from the human render — a convention became a property of the type. And `SKIPPED` is a real section, so D7's declared gaps reach the terminal instead of being buried in a file.

---

## D11 — Research before implementation, even when the answer seems obvious

**Decided:** Sprint 22 · **Artifact:** [RQ-0002](../research/RQ-0002-controller-lifecycle-hook-population.md)

Before writing any Sprint 22 code, the population question was investigated by measuring both real trees.

**What it caught:** **inheritance crosses repository boundaries.** 18 ERPNext controllers reach `Document` only through a base defined in `frappe`. Resolving ERPNext alone yields 492 where the truth is 510 — a silent 3.5% undercount.

**Why it matters that research caught it:** it is not a property of the collector. It is a property of *what one `EvidenceSet` is allowed to contain*, and it would otherwise have surfaced during implementation **as a wrong number rather than as a design question**. Four other plausible designs were also eliminated on measurement, including using DocType JSON count as the population.

---

## D12 — Extraction records facts; aggregation infers descent

**Decided:** Sprint 22 · **ADR:** [ADR-0015](../adr/ADR-0015-cross-repository-inheritance-resolution.md)

The collector records base names exactly as written and never decides whether a class descends from `Document`.

**Instead of:** resolving ancestry at extraction time and storing an `is_document_subclass` verdict — simpler for every consumer.

**Why:** it would freeze an inference inside a record whose entire contract is to state a fact, so improving the matching rule later would require re-extracting the whole corpus rather than re-running a resolver. It would also make extracting `erpnext` depend on `frappe` being checked out, so the same repository at the same commit could yield different Evidence on two machines.

---

## D13 — Supporting corpora resolve, they never join

**Decided:** Sprint 22 · **Enforced by:** the resolver's output shape

`AggregationRequest` separates `evidence_set` (the subject) from `supporting_evidence_sets` (context). A supporting corpus contributes class definitions and **nothing else** — no occurrence, no population membership, no `Pattern`.

**Instead of:** one collection of `EvidenceSet`s, merged — the obvious reading of "aggregate across corpora".

**Why:** merging produces Patterns spanning two repositories, which the platform forbids because the populations are differently constituted. `frappe`'s `NestedSet` explains why an ERPNext class is a controller; it does not thereby become one.

**How it is enforced:** `ClassDescentResult.descendants` simply does not contain supporting classes. A consumer cannot count one into a population because it is not there to count — a rule that cannot be broken rather than one that must be remembered. The same scoping was extended to `unresolved_bases` in the final commit, so **supplying more context can only shrink the residue, never grow it**.

---

## D14 — Two structural Evidence categories, not one

**Decided:** Sprint 22 · **Deviated from the approved brief, and said so**

`class_definition` and `class_base_declaration` are separate.

**Instead of:** a single "class X declares base B" category, which the approved scope specified.

**Why the deviation:** one category emits **nothing at all** for a class that declares no base — which is precisely the blind spot that made the lifecycle-hook population underivable in the first place. Reproducing that failure inside its own fix would have been a poor trade for a smaller enum. Recording the node set and edge set separately makes *every class produces at least one record* structural rather than remembered.

---

## D15 — Structural categories are topology, and sit outside the accounting

**Decided:** Sprint 22 · **Enforced by:** exclusion at partition time, plus an `aggregated + skipped == present` validator

`class_definition` and `class_base_declaration` have no row in the Capability Matrix and appear as neither measured nor skipped.

**Instead of:** letting them fall through to default-deny, which would have required no code at all.

**Why:** that files them as `SKIPPED_NO_POPULATION` — *"we could not measure this"* — when nobody tried, because there is nothing there to measure. **A declared gap that is not a gap devalues the ones that are**, and D7 is what the platform's credibility rests on.

---

## D16 — The schema version moves when the content does, not when the code does

**Decided:** Sprint 22, contracts stage · **Deviated from the approved brief, and said so**

`schema_version` was *not* bumped in the commit that added the new categories to the contract. It moved in the commit that first wrote artifacts containing them.

**Instead of:** bumping it with the contract change, as the brief asked.

**Why:** a version names what an artifact *may contain*. Between the contract change and the collector, no artifact could contain anything new — so every artifact produced in that window would have carried a label that was not true.

**Related finding, recorded not fixed:** `schema_version` is written by both engines and **checked by no reader**. Today a bump is a label, not a gate; an old reader rejects a new artifact because of `extra="forbid"` and a closed enum, which is the right outcome reached for an incidental reason. Enforcement is unclaimed work, not an assumed guarantee.

---

## D17 — Publish the correct number, and record how it was reached

**Decided:** Sprint 22, final stage

The committed ERPNext `PatternSet` uses `frappe` as resolution context — population **510**, not 492.

**Instead of:** aggregating ERPNext alone and disclosing the shortfall, which is closest to how the platform already handles what it cannot measure.

**Why not:** the platform *can* measure this now, and RQ-0002 measured exactly what would be discarded. **Disclosing an unknown and disclosing a known undercount are not the same act**; a platform that ships the second while capable of the first has redefined disclosure as an excuse.

**The cost, stated:** that artifact was produced through the API, because the CLI has no `--supporting` flag yet. `ResolutionProvenance` records which corpora contributed, so the figure is reproducible — but not yet by the shipped CLI. Adding the flag and regenerating through it is open work.

---

## D18 — The numerator must be drawn from the population, not compared to it

**Decided:** Sprint 22, Commit 7 · **Lives in:** `OCCURRENCE_FILTERS` · **Spec:** [Aggregation §5.1](evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md)

A behavioural occurrence contributes to `support` only when its subject entity is a member of the population defining that support.

**Instead of:** counting every record of a category, which is correct only when those records also define the population — true of `WHITELISTED_API_DECORATION`, false of `CONTROLLER_LIFECYCLE_HOOK`.

**Why it matters:** a hook record says a class defines a method with a lifecycle name; it does not say the class is a controller. Counting all of them against a denominator of `Document` descendants produced a ratio between two different sets — silently inflated on a large corpus, and an outright validation failure on a small one.

**Found by a consumer, not a test.** Commit 6's `--supporting` flag needed a fixture, and the fixture crashed. On the real corpus the same defect had been quiet: frappe's `validate` read `87/275` where the aligned figure is `84/275`. **The second time a consumer surfaced what 100% coverage did not** — see D8 for the first.

**Not a special case:** no repository name and no class name appears in the fix. Three frappe classes were excluded because they are not `Document` descendants, not because they were named.

**Clamping was explicitly rejected.** Capping support at `1.0` would have hidden the defect while leaving the number wrong.

---

## Decisions deliberately *not* taken

| Not done | Why not, and where it is tracked |
|---|---|
| Add `hrms` to `CanonicalRepository` | It is ranked #1 in this project's own source catalogue while the engine rejects it — but 90% adoption inside `frappe` means *this is the standard*, while 90% inside a consumer app means something else. Adding it before that is settled blurs a distinction the corpus cannot recover. [W3](evidence-platform/BACKLOG.md#w3--hrms-support) |
| Treat the author's own applications as corpus | Same reason, more sharply: they are personal-effort applications, not a standard |
| A `compare` command | Cross-repository populations are differently constituted, so no surface exists that would imply otherwise |
| Any LLM call in either engine | Zero, asserted by boundary tests scanning for provider imports. Extraction reads ASTs; aggregation counts |
