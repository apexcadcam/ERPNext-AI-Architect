# Sprint 24 Release Notes — HRMS Support

**Release:** `v1.5.0` — **pending, not yet tagged.**
**Outcome:** `hrms` is an admitted canonical repository with a committed corpus, measured under its complete supporting-corpus closure.
**Contract change:** `CanonicalRepository` gained a member; artifact schema moved `2.0 → 3.0`.
**Behaviour change:** aggregating `erpnext` without `frappe` is now refused.
**Depends on:** the Evidence Platform (`v1.1.0` Extraction, `v1.2.0` Aggregation, `v1.3.0` CLI, `v1.4.0` inheritance resolution, `v1.4.1` numerator alignment, `v1.4.2` ADR-0016)

---

## Summary

[W3](docs/evidence-platform/BACKLOG.md#w3--hrms-support) has been open since `v1.3.0`. It is closed.

**HRMS is an explicitly admitted canonical measured repository whose required supporting-corpus closure is `{erpnext, frappe}`.** That sentence is the release, and every word in it is load-bearing. HRMS is not measured; HRMS *measured under its established complete closure* is. Supplying anything less is refused rather than published, because the incomplete configurations do not fail — they produce a smaller, entirely plausible, wrong number.

The item was never really about editing an enum. It spent two releases blocked on a question that turned out to belong to a different layer, and was closed by research that found a completely different requirement underneath.

## Empirical basis

[RQ-0004](research/RQ-0004-hrms-as-a-measurable-repository.md) ran the existing collectors, unmodified, over the real HRMS tree at `031e97ba` and resolved its controller population in all four possible configurations:

| Configuration | Population | Unresolved bases | Hook owners outside the population |
|---|---|---|---|
| `hrms` alone | 143 | 10 | **6** |
| `hrms` + `frappe` | 145 | 6 | **4** |
| `hrms` + `erpnext` | 150 | 4 | **2** |
| **`hrms` + `frappe` + `erpnext`** | **153** | **0** | **0** |

**The collectors ran clean in all four.** 613 Python files, zero parse failures, 976 records, every time. Executability was never the problem.

**Why the incomplete three are refused rather than published.** They do not raise. A smaller denominator is a perfectly well-formed number, and Sprint 22's occurrence filter — which exists to keep the numerator inside the population — then quietly removes the 6, 4 or 2 real hook-bearing controllers that fell outside it. The result is a lower `support` figure with nothing anywhere indicating it is wrong. A reader holding `validate 62/145` has no way to tell it apart from `66/153`.

**Why both corpora, and not just the parent application.** One class settles it:

```
EmployeeMaster@hrms  ->  Employee@erpnext  ->  NestedSet@frappe  ->  Document
```

Neither supporting corpus alone resolves that chain. "Supply the parent app" is therefore not a correctness rule; the requirement is transitive closure over the ancestry graph, and it had to be measured rather than read off `required_apps`.

## Architecture

[ADR-0017](adr/ADR-0017-canonical-repository-admission.md) generalised the finding into a rule, and the rule is deliberately narrow:

- **Extractable is not measurable.** Four distinct states — extractable, researched, safely measurable, admitted — and only the last permits a canonical measurement. A repository does not qualify because the collectors can parse it.
- **Supporting closure is required, set-valued, and a minimum.** Declared per repository, established by measurement, recorded declaratively. More context is permitted and recorded; less is refused.
- **No dependency auto-discovery.** RQ-0004 established one repository's closure by measuring its ancestry graph. It did not prove a general algorithm, and inferring closure from packaging metadata was rejected as assuming the very thing the research had to measure.
- **Supporting corpora provide resolution context only.** They contribute class definitions so a chain leaving the measured repository can still be resolved — no occurrence, no population membership, no `Pattern` of their own. [ADR-0015](adr/ADR-0015-cross-repository-inheritance-resolution.md) is extended, not weakened.
- **The platform refuses; it never auto-injects.** A caller who omits required context is told exactly what to add. Filling it in silently would make an artifact's inputs implicit, which is the one thing `ResolutionProvenance` exists to prevent.
- **No `repository_role`.** W3 anticipated one. RQ-0004 found no *measurement* that needed it, and introducing an interpretive category into the producer is what [ADR-0016](adr/ADR-0016-no-automated-candidate-formation.md) forbids.

## Implementation sequence

Four reviewed steps, in an order chosen so that no intermediate commit could publish a wrong number:

**1. Policy enforcement, before any new repository existed.** A declarative admission registry — modelled on the Aggregation Capability Matrix rather than invented — and a generic precondition at the aggregation entry point, carrying only the closures that already existed: `frappe → {}` and `erpnext → {frappe}`. The engine consults it through a generic lookup exactly as it does `get_population_basis(category)`; no collector, resolver or engine branches on repository identity, and a boundary test asserts that the registry is the only module under `aggregation/` naming a repository at all.

**2. Admission, atomically.** `CanonicalRepository.HRMS` and its `{erpnext, frappe}` closure entry in a single commit. Splitting them would have created a state where HRMS was admitted with no closure — precisely the state in which aggregating it publishes 143 — and a completeness test now requires every enum member to carry an entry.

**3. Canonical provenance ordering.** Found during pre-publication validation, not after. Persisted `supporting_corpora` preserved the order the caller supplied. That is invisible while every artifact has at most one supporting corpus, and becomes a reproducibility defect the moment one has two: the same command with its flags typed the other way round would have written different bytes for an identical measurement. Now sorted by `(repository, version, commit)`, with the order carrying no precedence.

**4. Schema and corpus publication.** `2.0 → 3.0` in both producers, all three corpora regenerated under the current code, and the first committed HRMS artifacts.

## Published HRMS measurements

Source: `hrms` `15.51.0` at `031e97ba05ea9ba3250278450c58be01b7774f6a`.

| | Value |
|---|---|
| Python files parsed | **613** |
| Parse failures | **0** |
| Evidence records | **976** |
| Lifecycle population | **153** |
| `validate` | **66 / 153** |
| Whitelist population | **198** |
| `frappe.whitelist` | **198 / 198** |
| `unresolved_bases_count` | **0** |
| Strategy | `multi_corpus` |
| Supporting corpora | `erpnext v15.102.0`, `frappe v15.103.1` |
| Pattern owners | `hrms` only |

Every figure reproduces RQ-0004 exactly. Zero supporting-corpus classes entered the population and zero supporting-corpus records entered any numerator.

**A note on `613`.** That is Python files *parsed*. The walker examines the whole tree and skips everything that is not Python: `files_examined 59174 − files_skipped 58561 = 613`. The two metrics are far apart and must not be conflated.

**`frappe.whitelist 198/198` is tautological**, and is published as such. Every symbol in the whitelist population is there *because* it carries a whitelist-family decorator, so the ratio is a property of how the population is constructed, not a finding about HRMS. No recommendation is derived from it — nor from any other figure here.

## Regression: nothing else moved

| Repository | Lifecycle population | `validate` | `frappe.whitelist` | `validate_and_sanitize_search_inputs` | Unresolved |
|---|---|---|---|---|---|
| `frappe` v15.103.1 | **275** | 84/275 | 518/520 | 15/520 | 40 |
| `erpnext` v15.102.0 | **510** | 180/510 | 705/705 | 59/705 | 4 |

Both regenerated through the public CLI from the same pinned commits. Their `patterns.jsonl` files are **byte-identical** to their predecessors — every `pattern_id`, every ordering, every figure — and every `evidence_id` is unchanged in value and in position. The only differences are `schema_version` and the fields the contracts define as run-specific.

## Schema `3.0`

**`CanonicalRepository` is a closed vocabulary the artifacts are validated against, and it gained `hrms`.** That is the entire reason.

This is not a field-layout redesign. No `Evidence`, `Pattern`, `EvidenceSet` or `PatternSet` field was added, removed or retyped, and no measurement semantics changed. A `3.0` artifact can name a repository a `2.0` reader has never seen — in `EvidenceSet.repository`, `PatternSet.repository`, every `Pattern.repository` and every `CorpusRef` in `resolution_provenance` — and because these are closed enums, an old reader rejects such an artifact loudly rather than skipping the field. That is the correct outcome, and it is the same rule Sprint 22 applied when `EvidenceCategory` and `CollectorName` grew.

No migration machinery and no `2.x` compatibility aliases were introduced.

`frappe` and `erpnext` were regenerated at `3.0` rather than left at `2.0`, so the repository holds no artifact the current build cannot reproduce.

One correction landed with this: the aggregation producer's own comment said the version moves *"only"* when `PatternSet`'s fields change — narrower than the evidence producer's stated policy, and it would have argued against this bump. The two write artifacts validated by the same enums, so the comment was corrected rather than worked around.

## Reproducibility

The public CLI reproduces all three committed Pattern artifacts byte-for-byte from the committed Evidence:

```bash
architect patterns aggregate frappe  --version v15.103.1
architect patterns aggregate erpnext --version v15.102.0 --supporting frappe:v15.103.1
architect patterns aggregate hrms    --version 15.51.0 \
    --supporting frappe:v15.103.1 \
    --supporting erpnext:v15.102.0
```

**Supporting flag order does not affect the result.** Generating the HRMS artifact with the two flags in both orders produces byte-identical `patterns.jsonl` files and — once the four run-specific metadata fields are pinned — byte-identical metadata. Persisted provenance is canonically ordered, so `erpnext` appears before `frappe` regardless. That order is alphabetical, not architectural.

Refusals were confirmed against the real corpus: `erpnext` alone names `frappe`; `hrms` alone names both; `hrms` with either single corpus names the other.

## Tests

**2,521 passing.** `aggregation/` and `evidence/` remain at **100% coverage**. `mypy --strict` clean across the sprint scope; `ruff check` and `ruff format --check` clean on every file touched.

**A new committed-corpus regression layer**, and it closes a real gap: until this sprint, *nothing in the suite read `evidence-data/` or `pattern-data/` at all*. Every published figure had been verified by hand, once, at release time — so a regeneration that silently moved a denominator would have passed the entire suite. RQ-0004 is exactly why that matters.

`tests/test_committed_corpus.py` reads the committed artifacts and asserts the published measurements, the schema label, the resolution context behind each population, pattern ordering, ID uniqueness, category accounting, corpus pairing, that no supporting-corpus record was counted as an occurrence, and that every `CanonicalRepository` member has a committed corpus.

**What it deliberately is not.** It is not a golden-file copy of every Pattern line — the artifacts are already the detailed record. It does not recompute a population or resolve descent; that proof stays with the resolver tests, where the input is controlled. And it **does not fetch repositories, re-run extraction against upstream source trees, or prove the pinned upstream commits still exist.** It loads six committed files.

## What did not change

No collector, no inheritance resolver, no population resolver, no occurrence filter, no aggregation arithmetic, no persistence model, no CLI flag or command. The resolver was measured running unmodified across three corpora rather than two.

Production Python across the whole sprint is a registry module, a contract record type, one precondition call, one sort key, and two schema constants.

## Non-goals — what this release does *not* provide

Stated explicitly, because "HRMS support" invites every one of these readings:

- **Arbitrary Frappe-app admission.** Default deny is unchanged. The enum stays closed, and each further repository costs its own research question. The author's own applications remain permanently out of corpus: they are personal-effort software, not a standard.
- **Automatic dependency discovery.** Closures are measured and registered, never inferred.
- **Auto-injected context.** Omitting a required corpus is an error, not a hint.
- **Normative interpretation.** Admission says a measurement is well-defined and reproducible. `validate` reads 84/275 in frappe, 180/510 in erpnext and 66/153 in HRMS — structurally comparable *measurements*, never comparable recommendations. Framework-versus-consumer is a claim, and claims live downstream in Research and human Architecture Review.
- **Candidate Formation.** ADR-0016 stands. No engine turns a Pattern into a Candidate Rule.
- **Auto-generated Engineering Rules.** None. Nothing in this release proposes a rule, and RQ-0004 proposed none.

## Known limitations

Unchanged from `v1.4.2` except that W3 is now closed — see the [Evidence Platform backlog](docs/evidence-platform/BACKLOG.md). [W10](docs/evidence-platform/BACKLOG.md#w10--version-string-format-consistency) is now visible in the committed corpus rather than hypothetical: `hrms-15.51.0.*` sits beside `frappe-v15.103.1.*`. It stays open and non-blocking, and was deliberately kept out of this sprint — normalising a version string would change artifact identity.

## A note on method

Two things in this sprint were found by *consuming* the platform rather than by testing it, and both are now the third and fourth entries in that pattern.

The provenance-ordering defect was found while preparing to publish the first two-supporting-corpus artifact. No test failed; nothing was wrong with any measurement. It surfaced only because someone asked what the artifact would look like if the flags were typed the other way round.

And the absence of committed-corpus regression coverage was found by reading the repository during planning, not by any failure. The published figures had been correct for four releases — protected by attention, which is not a mechanism.
