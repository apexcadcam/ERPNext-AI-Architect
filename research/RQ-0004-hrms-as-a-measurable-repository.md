# HRMS as a Measurable Repository

## Status

- Date opened: 2026-08-01
- Date closed: 2026-08-01
- Status: `Resolved` — accepted at review; the architectural rule it framed is recorded in [ADR-0017](../adr/ADR-0017-canonical-repository-admission.md).

**Changelog**
- 2026-08-01 — Opened and investigated (RQ-0004). Measures HRMS 15.51.0 at commit `031e97ba` against the existing Evidence Platform architecture, to answer [W3](../docs/evidence-platform/BACKLOG.md#w3--hrms-support).
- 2026-08-01 — Accepted at review. Findings unchanged. The generalised rule — repository admission and transitive supporting-corpus closure — is recorded in [ADR-0017](../adr/ADR-0017-canonical-repository-admission.md).

## Question

**Can HRMS be added as a first-class measurable repository to the Evidence Platform without introducing repository-specific semantics, and what supporting corpora are required to measure it correctly?**

## Background

[W3](../docs/evidence-platform/BACKLOG.md#w3--hrms-support) has been open since the `v1.3.0` backlog: `hrms` is ranked `KS-0033` / rank #1 / P0 in this project's own committed [source catalogue](../knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) while `CanonicalRepository` rejects it. W3 recorded the exclusion as an implementation shortcut rather than an architectural invariant, and blocked it on a design question: framework-versus-consumer semantics.

## Method

Measured against the real tree at `/home/gaber/frappe-bench/apps/hrms`. Identity verified before measurement: `git rev-parse HEAD` = `031e97ba05ea9ba3250278450c58be01b7774f6a`, and `hrms/__init__.py` declares `__version__ = "15.51.0"`.

The existing collectors were **imported and run unmodified**. Because `CanonicalRepository` has no `hrms` member, probes labelled HRMS with an existing enum value; this affects `evidence_id` hashing only, never a count, a population, or an invariant.

The three-corpus configuration cannot be expressed through `resolve_descent` with only two enum members, so an independent implementation of the same documented semantics was written and **validated against the real resolver on both expressible configurations** — identical descendant sets, unresolved lists and depths.

## Findings

### F1 — HRMS is an ERPNext-dependent Frappe application, established from source

| Signal | Evidence |
|---|---|
| Imports | `frappe` 890 · `erpnext` 166 · `hrms` 457 |
| Inheritance-relevant | `erpnext.controllers.accounts_controller`, `erpnext.setup.doctype.employee.employee` |
| `hooks.py` | `required_apps = ["frappe/erpnext"]` |

The dependency on `erpnext` is **structural**, not merely declarative — F3 shows 8 HRMS controllers whose ancestry passes through ERPNext base classes.

### F2 — The existing collectors run clean, with no repository-specific behaviour

**613 files examined, 0 parse failures, 976 records.**

| Category | Records |
|---|---|
| `class_base_declaration` | 303 |
| `class_definition` | 301 |
| `whitelisted_api_decoration` | 206 |
| `controller_lifecycle_hook` | 166 |

No collector failed on HRMS syntax, and a repository-wide grep confirms **no engine anywhere branches on repository identity**.

### F3 — Population depends on resolution context, and only the full closure is correct

| Configuration | Population | Max depth | Unresolved | Hook owners outside population |
|---|---|---|---|---|
| HRMS alone | 143 | 1 | 10 | **6** |
| HRMS + frappe | 145 | 1 | 6 | **4** |
| HRMS + erpnext | 150 | 6 | 4 | **2** |
| **HRMS + frappe + erpnext** | **153** | 6 | **0** | **0** |

The decisive chain:

```
EmployeeMaster@hrms -> Employee@erpnext -> NestedSet@frappe -> Document@frappe
```

**Neither supporting corpus alone resolves it.** 8 classes cross HRMS → ERPNext → Frappe; 2 cross HRMS → Frappe directly (`Goal`, `JobOpening`). "Supply the parent application" is therefore not a sufficient correctness rule — the requirement is transitive closure.

### F4 — Incomplete context fails silently, not loudly

69 HRMS classes bear a lifecycle hook. Under the full closure all 69 sit inside the 153-class population, so `occurrence_symbols ⊆ population_symbols` holds and nothing is filtered.

**Under every partial configuration the invariant fails** — 6, 4, then 2 hook-bearing classes fall outside the population. Sprint 22's occurrence filter would silently drop those real controllers from the numerator, producing a lower, wrong support figure **rather than an error**.

This is a second route to the same class of defect Sprint 22 Commit 7 fixed: that was a mis-scoped numerator; this is an under-resolved denominator.

### F5 — ADR-0015's containment invariant holds, verified not assumed

| Invariant | Measured |
|---|---|
| Population ⊆ HRMS-defined symbols | True |
| Supporting-corpus symbols inside the population | **0** |
| Supporting-corpus hook records in the numerator | **0** |

### F6 — The Capability Matrix remains semantically valid, not merely executable

`controller_lifecycle_hook`'s population is "classes descending from `frappe.model.document.Document`". `Document` is the same class in all three corpora; HRMS reaches it through longer chains the resolver already handles to depth 6. `whitelisted_api_decoration` is constructed identically, with the identical tautology.

Under the full closure HRMS would publish `validate 66/153`, `on_submit 28/153`, `on_cancel 27/153`, and seven more down to `on_trash 2/153`.

### F7 — Whitelist population behaves exactly as RQ-0003 established

Denominator **198**. `frappe.whitelist` **198/198** — tautological for the same structural reason, since HRMS uses the bare `whitelist` spelling zero times. `frappe.validate_and_sanitize_search_inputs` 6/198; `cache_source` 2/198. **No recommendation is derived from any of these frequencies.**

### F8 — The required change is identity only

Every repository name in the CLI derives from `CANONICAL_REPOSITORY_NAMES`, which derives from the enum. `ResolutionProvenance.supporting_corpora` is `tuple[CorpusRef, ...]` with no cap — verified by inspecting both it and `AggregationRequest` for `max_length`/`max_items`. Two supporting corpora need **no schema change**. `Source.commit`'s `^[0-9a-f]{7,40}$` accepts HRMS's 40-character commit.

### F9 — W3's stated blocker was already dissolved by ADR-0016

W3 was blocked on framework-versus-consumer semantics, a framing that assumed the platform makes normative claims. [ADR-0016](../adr/ADR-0016-no-automated-candidate-formation.md) removed that assumption: support is descriptive frequency, eligibility is claim-relative, the producer records construction facts only.

`validate` is `84/275` in frappe, `180/510` in erpnext, `66/153` in HRMS — **identically constructed measurements**. Only a human-authored claim could confuse framework with consumer, and claims already sit behind Research and Architecture Review.

## Evidence Summary

HRMS is measurable by the existing architecture with no engine change, provided both `frappe` and `erpnext` supply resolution context. The closure was established by **measurement, per repository** — nothing in this research yields a general algorithm for discovering it.

## Open Questions

1. Should the researched closure be enforced or merely documented? **Settled by [ADR-0017](../adr/ADR-0017-canonical-repository-admission.md): enforced**, because F4 shows incomplete context fails silently.
2. Does a repository whose measurement is technically executable thereby become measurable? **Settled by ADR-0017: no.**
3. Version-string format differs between corpora (`v15.103.1` vs `15.51.0`). No contract constrains it — `version` is `Field(min_length=1)` everywhere. Left open as [W10](../docs/evidence-platform/BACKLOG.md#w10--version-string-format-consistency).

## Final Recommendation

**Approve HRMS admission, conditional on both supporting corpora being required in practice rather than merely documented.**

HRMS measured with fewer than both produces a plausible, silently wrong population — 143, 145 or 150 instead of 153 — and drops up to 6 real controllers from the numerator without raising anything.

## Potential Rule Candidates

**None.** This research concerns the platform's own measurement capability, not how an ERPNext developer should build something. Consistent with ADR-0016, no evidence-derived Engineering Rule is proposed.

## Related Topics

- [ADR-0017](../adr/ADR-0017-canonical-repository-admission.md) — the rule this research framed
- [ADR-0015](../adr/ADR-0015-cross-repository-inheritance-resolution.md) — the containment invariant F5 verifies
- [ADR-0016](../adr/ADR-0016-no-automated-candidate-formation.md) — why F9's blocker dissolved
- [W3](../docs/evidence-platform/BACKLOG.md#w3--hrms-support) — the backlog item this answers

## References

Tier 1, measured directly:

- `hrms` 15.51.0 at `031e97ba05ea9ba3250278450c58be01b7774f6a` — 613 `.py` files
- `evidence-data/frappe-v15.103.1.*`, `evidence-data/erpnext-v15.102.0.*` — committed corpora used as resolution context
- `evidence/collectors.py`, `aggregation/inheritance.py`, `aggregation/resolvers.py` — run unmodified
