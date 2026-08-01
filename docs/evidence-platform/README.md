# The Evidence Platform

> ERPNext-AI-Architect does not learn from a language model. It learns from verifiable evidence extracted from the ERPNext ecosystem, with every architectural conclusion traceable back to its source.

That sentence is the platform's reason for existing. The language model consumes and communicates knowledge; it does not produce it. What follows is how that is enforced in code rather than asserted in prose.

## The chain

```
canonical repository  →  Evidence Extraction  →  EvidenceSet   (evidence-data/)
                                                     ↓
                                              Pattern Aggregation  →  PatternSet  (pattern-data/)
                                                     ↓
                                              architect patterns report
```

One-directional. Aggregation consumes the *persisted* `EvidenceSet` and is structurally forbidden from importing the extraction engine — a boundary test checks this by exact dotted path, because `evidence.contract` is allowed while `evidence.engine` is not and both begin with `evidence`.

## Documents

| Document | Covers |
|---|---|
| [`EVIDENCE_EXTRACTION_SPECIFICATION.md`](EVIDENCE_EXTRACTION_SPECIFICATION.md) | What a fact is, how it is traced, and what is deliberately not collected |
| [`PATTERN_AGGREGATION_SPECIFICATION.md`](PATTERN_AGGREGATION_SPECIFICATION.md) | What a measurement is, when a denominator exists, and what happens when it does not |
| [`CLI_SPECIFICATION.md`](CLI_SPECIFICATION.md) | The `architect` command surface and the Output Contract |
| [`INHERITANCE_RESOLUTION_SPECIFICATION.md`](INHERITANCE_RESOLUTION_SPECIFICATION.md) | **Sprint 22, implemented** — how the lifecycle-hook denominator became derivable |
| [`BACKLOG.md`](BACKLOG.md) | Open work items, with what "done" means for each |

Section numbers cited in the source (`§2`, `§7.3`, …) refer to these documents.

## Running it

```bash
# frappe -- closure is empty, so no context is required
architect evidence extract frappe --version v15.103.1 --commit 61ab7e2b2409b293ffd3c8f72d730fa89b201332
architect patterns aggregate frappe --version v15.103.1

# erpnext -- requires frappe as resolution context
architect evidence extract erpnext --version v15.102.0 --commit 1d14ba16398db3a220873509565c60f2932bed81
architect patterns aggregate erpnext --version v15.102.0 --supporting frappe:v15.103.1

# hrms -- requires BOTH, and is refused with either one missing
architect evidence extract hrms --version 15.51.0 --commit 031e97ba05ea9ba3250278450c58be01b7774f6a
architect patterns aggregate hrms --version 15.51.0 \
    --supporting frappe:v15.103.1 \
    --supporting erpnext:v15.102.0

architect patterns report hrms --version 15.51.0
```

Those are the exact commands that reproduce the three committed Pattern
corpora. Nothing is inferred: the supporting corpora are typed out because the
platform will not add them for you, and omitting one is an error rather than a
smaller number. Flag order does not matter — persisted provenance is sorted
canonically, so the artifact does not depend on how the command was typed.

Every command emits the same six sections — `SUMMARY`, `ARTIFACTS WRITTEN`, `WARNINGS`, `SKIPPED`, `ERRORS`, and an exit code — in that order, always, including the empty ones. `--json` renders the same object as machine-readable output.

## The two ideas worth knowing before reading the code

**Atomic evidence.** One record per single observed fact. A function carrying three decorators produces three records, never one bundled record. This is what later makes counting distinct symbols both cheap and honest.

**A skip is a result, not a message.** When the platform can see a signal but cannot honestly measure it, that fact becomes a typed, persisted `SkippedAggregation` carrying the full reason — asserted on by tests and printed in full by the CLI. The alternative, staying silent, would make "we cannot measure this" indistinguishable from "there is nothing here".

The clearest example ran for two releases. The controller-lifecycle-hook denominator was not derivable — the collector emits a record only where a hook was *found*, so classes without hooks left no trace and the numerator existed while the population did not. Rather than divide anyway, the platform recorded a `SkippedAggregation` naming the gap, the measured lower bound, and the work that would close it.

Sprint 22 closed it: class-definition Evidence made the class graph visible, and an inheritance resolver turned it into a population. The declaration was not withdrawn — it was **earned out**. That is the intended lifecycle of every gap this platform declares.

## Current limits

- Three repositories (`frappe`, `erpnext`, `hrms`) — `CanonicalRepository` is a
  closed enum, and stays closed. A repository is admitted only after research
  has established what its denominators mean and which corpora resolve them
  ([ADR-0017](../../adr/ADR-0017-canonical-repository-admission.md)); it is not
  admitted because the collectors can parse it. Arbitrary Frappe applications
  are **not** supported.
- Both behavioural categories now have a derivable denominator. The
  lifecycle-hook population was the platform's one declared gap from
  `v1.2.0`; Sprint 22 closed it by adding class-definition Evidence and an
  inheritance resolver, so the `SKIPPED` section is now empty **because the
  measurement exists**, not because the declaration was withdrawn.
- **Each repository has a required supporting-corpus closure, and it is
  enforced.** `frappe` needs none. `erpnext` requires `frappe`: 18 of its
  controllers reach `Document` only through a frappe-defined base, so
  aggregating it alone would yield 492 against a true 510 — that invocation is
  now refused rather than published. `hrms` requires **both** `erpnext` and
  `frappe`, and neither alone is a partial improvement: it resolves 143, 145 or
  150 instead of 153, silently dropping real controllers from the numerator.
  The platform refuses and names what is missing; it never supplies the corpora
  for you. `PatternSet.resolution_provenance` records which corpora actually
  contributed.
- Cross-repository comparison is deliberately undefined and has no command surface.
- Re-extraction reproduces every `evidence_id` and every non-timestamp field identically, but the Evidence JSONL is not byte-identical because each record carries a `collected_at` timestamp. Pattern artifacts *are* byte-identical.
