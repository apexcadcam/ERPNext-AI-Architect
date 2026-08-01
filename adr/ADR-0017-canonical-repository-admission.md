# ADR-0017: Canonical Repository Admission and Supporting-Corpus Closure

**Date:** 2026-08-01
**Status:** Accepted
**Evidence:** [RQ-0004](../research/RQ-0004-hrms-as-a-measurable-repository.md) — HRMS 15.51.0 at `031e97ba`, 613 files, 976 records
**Extends:** [ADR-0015](ADR-0015-cross-repository-inheritance-resolution.md) — context selection, without weakening containment
**Bounded by:** [ADR-0016](ADR-0016-no-automated-candidate-formation.md) — admission asserts nothing normative
**Resolves the architectural blocker in:** [W3](../docs/evidence-platform/BACKLOG.md#w3--hrms-support)

## Context

W3 has been open since `v1.3.0`, blocked on framework-versus-consumer semantics. [RQ-0004](../research/RQ-0004-hrms-as-a-measurable-repository.md) investigated it and returned something broader than "add `hrms` to the enum".

**A repository can be fully parseable and still not be safely measurable.** Measured against the real HRMS tree:

| Configuration | Population | Unresolved | Hook owners outside population |
|---|---|---|---|
| HRMS alone | 143 | 10 | **6** |
| HRMS + `frappe` | 145 | 6 | **4** |
| HRMS + `erpnext` | 150 | 4 | **2** |
| HRMS + `frappe` + `erpnext` | **153** | 0 | **0** |

The collectors run clean on all 613 files with zero parse failures in *every* configuration. The difference is not executability — it is whether the denominator is complete. And the failure is **silent**: under partial context, Sprint 22's occurrence filter drops real controllers from the numerator and publishes a lower, plausible, wrong support figure rather than raising.

The decisive case is one class:

```
EmployeeMaster@hrms -> Employee@erpnext -> NestedSet@frappe -> Document@frappe
```

Neither supporting corpus alone resolves it. **"Supply the parent application" is therefore not a correctness rule.** The requirement is transitive closure over the ancestry graph, and RQ-0004 established HRMS's closure by measurement — not by reading `required_apps`, and not by any general algorithm.

## Decisions

### 1. Four distinct states, and only the last permits canonical measurement

A repository may be:

| State | Meaning |
|---|---|
| **Extractable** | The collectors parse it and emit records. Says nothing about correctness. |
| **Researched** | Its measurement semantics have been examined against the Capability Matrix, and its supporting-corpus closure has been established by measurement. |
| **Safely measurable** | Under the researched closure, the platform's correctness invariants hold — in particular `occurrence_symbols ⊆ population_symbols`. |
| **Admitted** | Recorded as a `CanonicalRepository` member with its closure registered. |

**Extractable is not measurable.** HRMS was extractable in all four configurations and safely measurable in exactly one.

Admission requires all of: semantics valid under the existing Capability Matrix; closure known; invariants satisfied under that closure; and supporting corpora contributing resolution context only, per ADR-0015.

### 2. Supporting-corpus closure is transitive, declared per repository, and is a minimum

Closure is **not** modelled as `consumer → framework`, nor as one parent per repository. RQ-0004 disproves both: HRMS needs two corpora, and one of its classes needs both simultaneously.

**A repository's closure is the set of corpora required to resolve its measured populations completely — determined by research, recorded declaratively.**

The registered closure is a **minimum, not a maximum**. Supplying additional context is permitted and recorded; supplying less is refused (§4).

**Separate the requirement from the corpus that satisfies it.** The repository-level semantic requirement is *"HRMS requires `erpnext` and `frappe` as resolution context."* The particular versions used to satisfy it — `erpnext v15.102.0`, `frappe v15.103.1` — are a property of a **run**, recorded in `ResolutionProvenance`, not a permanent global default. Pinning versions into the registry would make the registry a corpus manifest, which it is not.

### 3. Closure is enforced, not merely documented

**Tested against R009 before adopting.** R009 forbids *speculative* infrastructure. This is not speculative: RQ-0004 measured a real, silent, wrong-number failure mode. It is demand-triggered by evidence, which is the same standard [ADR-0016](ADR-0016-no-automated-candidate-formation.md) applied when it declined to build a component the corpus did not justify. The asymmetry is deliberate and consistent: build when measurement demands it, not when a roadmap does.

Documentation alone was rejected because the failure is silent. A convention that must be remembered protects nothing when forgetting it produces a plausible number instead of an error — the same reasoning that made ADR-0015 enforce containment through the resolver's output shape rather than through a comment.

### 4. Enforcement ownership: a declarative registry, consulted generically

**Native-first search performed first.** Every existing registry — `POPULATION_BASES`, `POPULATION_RESOLVERS`, `OCCURRENCE_FILTERS`, `STRUCTURAL_CATEGORIES` — is keyed by `EvidenceCategory` or is a scalar. **None is keyed by repository.** Plugin manifests describe *modules*, not repositories. `runtime/config` is domain-agnostic by `RUNTIME_ARCHITECTURE.md §1` and must not learn ERPNext repository semantics. `CanonicalRepository` carries identity only.

There is no existing owner. A new one is justified, and it is **modelled on the Capability Matrix rather than invented**: a declarative registry stating, per repository, what its measurement requires — exactly as `POPULATION_BASES` states, per category, what its measurement requires.

**Minimum semantics only:** a mapping from repository to its required supporting repositories, with a justification and a pointer to the research that established it. Nothing else. **This is not a repository plugin system** — no lifecycle, no discovery, no capabilities, no code per repository.

**No engine gains a repository-specific branch.** The engine performs a generic lookup, exactly as it already does with `get_population_basis(category)`. Constructs of the form `if repository == HRMS: require frappe and erpnext` are forbidden in collectors, the inheritance resolver, population resolvers and the aggregation engine, and are unnecessary: the branch is **data**, not code. A repository with an empty closure — `frappe` — needs no special case either.

### 5. API and CLI behaviour

| Caller supplies | Behaviour | Owner |
|---|---|---|
| **No supporting corpora**, closure non-empty | **Refuse**, naming exactly what is missing | new rule |
| **Partial closure** | **Refuse**, naming exactly what is missing | new rule |
| **Exact closure** | Proceed; provenance records it | existing |
| **Closure plus extra corpus** | **Permit**, recorded in provenance — closure is a minimum, and extra context can only be judged by what provenance shows | new rule |
| **Duplicate corpora** | Already rejected — `AggregationRequest` rejects a repeated repository as ambiguous | **existing, not restated** |
| **Measured repository as its own support** | Already rejected — `AggregationRequest` and `resolve_descent` both refuse it | **existing, not restated** |

Two of the six cases are already handled by validators written in Sprint 22. This decision adds rules only for the four that are not.

**The platform refuses; it never auto-injects.** A caller who omits required context is told what to add and re-runs the command. Automatic injection was rejected: it would make the artifact's inputs implicit, and the whole reason `ResolutionProvenance` exists is that `153` and `143` are both defensible numbers distinguishable *only* by what was supplied. Convenience is not worth making provenance describe a decision the platform made silently.

### 6. Correctness precondition — and what it is *not*

**Satisfying the registered closure is a precondition for publishing a canonical measurement.** It sits alongside the Sprint 22 membership invariant rather than replacing it:

- Sprint 22 Commit 7 fixed a **mis-scoped numerator** — occurrences drawn from outside the population.
- RQ-0004 identifies an **under-resolved denominator** — a population smaller than the truth, which then silently filters valid occurrences out.

Both endanger `occurrence_symbols ⊆ population_symbols`; they arrive from opposite directions.

**`unresolved_bases_count == 0` is explicitly rejected as an admission rule.** HRMS happens to reach zero under full closure, but that is incidental. Legitimate repositories contain stdlib and third-party bases — `ABC`, `Enum`, `Exception` — unrelated to `Document` ancestry; `frappe`'s own residue is 40. The requirement is **semantic completeness of the relevant population**, established by research, not the elimination of every unresolved name.

### 7. ADR-0015 is extended, not weakened

Supporting corpora still contribute class definitions and base declarations for inheritance resolution **and nothing else** — no occurrence, no population membership, no `Pattern` ownership. RQ-0004 verified this empirically for HRMS: **zero** supporting symbols entered its population and **zero** supporting hook records entered its numerator, with 675 supporting class definitions available.

This decision governs **which** corpora are supplied. ADR-0015 governs **what they may do** once supplied. The second is untouched.

### 8. ADR-0016 is intact; admission is not a normative act

**Repository admission says measurements are well-defined and reproducible. It does not say measured frequencies are standards, recommendations, or Rule-grade evidence.**

`validate` is `84/275` in `frappe`, `180/510` in `erpnext`, `66/153` in HRMS. These are **structurally comparable measurements**; they are **not comparable recommendations**. Framework-versus-consumer interpretation is a claim, and claims live downstream in Research and human Architecture Review.

**No `repository_role` field is introduced.** W3 anticipated one, but RQ-0004 found no *measurement* need: the Capability Matrix is semantically valid over HRMS without knowing what kind of repository it is. Introducing a role would put an interpretive category into the producer, which decision 6 of ADR-0016 forbids. It may be revisited if a measurement — not an interpretation — ever requires it.

### 9. Generalisation boundary

This decision establishes that **another explicitly registered repository can become measurable after its semantics and supporting-corpus closure have been researched.** It does **not** establish that arbitrary Frappe applications are supported.

**Default deny is unchanged.** The closed `CanonicalRepository` enum already expresses it, and this decision adds a second gate rather than opening the first: a repository is measurable when someone has established what its denominators mean and what context resolves them — not because it happens to parse.

**No automatic dependency-closure discovery is introduced.** RQ-0004 established HRMS's closure by measuring its ancestry graph; it did not prove a general algorithm for discovering safe measurement context. An application depending on HRMS would plausibly need a third transitive layer, and that would have to be researched too.

## Consequences

**HRMS becomes admissible, but is not thereby admitted.** This ADR authorises the rule; implementation is separate and unstarted.

**`erpnext`'s existing closure becomes explicit and enforced.** Its committed corpus is already aggregated with `frappe` supplied, so no published figure changes — but aggregating `erpnext` alone, which was possible during Sprint 22 research and yields 492, would become a refusal. That is a deliberate behaviour change and must be disclosed when implemented.

**`frappe` has an empty closure** and is unaffected.

**Every future repository costs a research question.** That is the intended cost. It is what distinguishes this platform's claims from a tool that measures whatever it can parse.

**Provenance carries more weight.** Because closure is a minimum and extra context is permitted, `ResolutionProvenance` is the only place a reader can see which corpora actually produced a population.

## Rejected alternatives

**1. Add HRMS to the enum and rely on users to remember both `--supporting` flags.** Rejected: RQ-0004 shows forgetting produces `143` instead of `153` and silently drops 6 controllers, with no error. A convention cannot protect an invariant whose violation is invisible.

**2. Hard-code HRMS dependencies in aggregation or resolver logic.** Rejected: it would put repository identity inside generic engines, which currently contain none — verified by grep across `evidence/`, `aggregation/`, `composition_root/` and `runtime/`. The registry keeps the knowledge declarative and the engines generic.

**3. Assume one supporting corpus per measured repository.** Rejected on measurement. `EmployeeMaster` needs `erpnext` *and* `frappe`; a single-parent model resolves 145 or 150, never 153.

**4. Automatically infer closure from imports or `required_apps`.** Rejected as unproven. HRMS's `required_apps = ["frappe/erpnext"]` happens to name both, but RQ-0004 established the closure from the **ancestry graph**, not from metadata — and metadata is a packaging declaration, not a statement about which classes a population needs. Inferring closure from it would be assuming the very thing RQ-0004 had to measure. Revisit only if research demonstrates the inference is sound.

**5. Require `unresolved_bases_count == 0` for every canonical repository.** Rejected: `frappe`'s own residue is 40 legitimate stdlib and third-party bases. A zero rule would disqualify the framework itself.

**6. Introduce `repository_role` and branch measurement semantics on it.** Rejected: no measurement needs it (§8), and it would reintroduce interpretation into the producer contrary to ADR-0016.

**7. Treat any repository the collectors can parse as measurable.** Rejected — this is the alternative the whole ADR exists to refuse. HRMS parsed cleanly in all four configurations and was correct in one.

## Implementation implications — recorded, not implemented

Nothing here is built. When implementation is authorised, RQ-0004 F8 measured the surface as:

| Surface | Change | Class |
|---|---|---|
| `CanonicalRepository` | one enum member | required |
| Repository closure registry | new declarative module, Capability-Matrix-shaped | required |
| Closure enforcement | generic lookup at the aggregation entry point | required |
| Two conformance tests | closed-set assertions, updated deliberately | required |
| Corpus artifacts | `hrms-15.51.0.*` in both data directories | required |
| Documentation | Capability Matrix, platform README, backlog, release notes | required |
| Collectors / resolver / population resolvers / persistence | **none** — measured working unmodified | not required |
| Composition root / CLI | **none** — names derive from the enum; `--supporting` is already repeatable | not required |
| `ResolutionProvenance` schema | **none** — `supporting_corpora` is an uncapped tuple | not required |
| `repository_role` | **none** | not required |

## Notes

RQ-0004 is preserved unchanged as the empirical basis. Where this ADR and the research disagree, the research is the measurement and this document is the judgement.

The version-string inconsistency RQ-0004 observed — committed corpora use `v15.103.1` while HRMS declares `15.51.0` — is **not** resolved here. No contract constrains the format; `version` is `Field(min_length=1)` throughout. It is recorded as [W10](../docs/evidence-platform/BACKLOG.md#w10--version-string-format-consistency) and deliberately kept out of HRMS support, because silently normalising a version string would alter artifact identity.
