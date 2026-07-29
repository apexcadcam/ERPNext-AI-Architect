# ADR-0015: Resolve Cross-Repository Inheritance in the Aggregation Layer, Not the Extractor

**Date:** 2026-07-29
**Status:** Accepted
**Supersedes:** the open design question in [RQ-0002](../research/RQ-0002-controller-lifecycle-hook-population.md#open-questions)
**Enables:** [W5 — Sprint 22 denominator work](../docs/evidence-platform/BACKLOG.md#w5--sprint-22-denominator-work)

## Context

[RQ-0002](../research/RQ-0002-controller-lifecycle-hook-population.md) established, by measurement against the pinned trees, that the `controller_lifecycle_hook` population is statically derivable — no class in either repository has a base expression an AST cannot resolve, across 3,800 files and 1,938 class definitions.

It also found the constraint that makes this decision necessary. **Inheritance crosses repository boundaries.** 18 ERPNext controllers descend from `Document` only via a base class defined in `frappe` — `NestedSet` (14 subclasses) and `WebsiteGenerator` (2) among them. Resolving ERPNext's population from its own `EvidenceSet` alone yields 492 where the true figure is 510: a silent 3.5% undercount.

`frappe` shows zero such cases. That is structural, not incidental — the framework has nothing upstream to inherit from — so **the dependency is one-directional, and so is the error**.

Three options were carried into review: resolve ancestry at extraction time; aggregate over a set of `EvidenceSet`s; or resolve per-repository and declare the residue.

## Decision

**Option 2. Extraction records raw facts; the Aggregation layer resolves inheritance and derives populations, because it is the layer that legitimately holds context wider than one repository.**

Concretely:

1. **The new Evidence category records declared base class names, verbatim.** One atomic record per class definition, carrying the names as written in the source. The collector performs **no resolution and asserts no descent** — it does not decide whether a class is a `Document` subclass, because at the moment it reads `class Sales Invoice(SellingController)` it genuinely does not know, and a collector that guesses is a collector that can be wrong in a way nothing downstream can detect.

2. **Aggregation resolves descent transitively across every corpus it is given**, and derives the population from the resolved graph.

3. **The subject of a `PatternSet` remains exactly one repository.** This is the refinement below, and it is the part of this decision that is not simply "Option 2 as written".

### The refinement: supporting corpora are not additional subjects

"Aggregate over a set of `EvidenceSet`s" has an obvious reading that would be wrong: make `AggregationRequest` take a collection and merge them. That would produce Patterns spanning two repositories, which [Aggregation §4](../docs/evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md) explicitly forbids — cross-repository comparison is undefined precisely because the populations are differently constituted.

The two roles are distinct and must stay distinct in the type:

```python
evidence_set: EvidenceSet                                # the subject — measured, unchanged
supporting_evidence_sets: tuple[EvidenceSet, ...] = ()   # resolution context only
```

A supporting corpus contributes **class definitions used to resolve inheritance and nothing else**. It never contributes occurrences, never contributes to a population count, and never produces a `Pattern` of its own. `frappe`'s `NestedSet` explains why an ERPNext class is a controller; it does not thereby become part of ERPNext's population, nor ERPNext part of `frappe`'s.

This keeps the existing guarantee intact: one `PatternSet`, one repository, no implied comparability.

### Provenance must record what was used

If a population can now be derived using more than one corpus, then **510 and 492 are both defensible numbers that differ only by what was supplied** — and a stored `PatternSet` that does not say which is a `PatternSet` whose central figure cannot be reproduced or audited. The artifact must therefore record the supporting corpora that contributed to resolution, identified by repository, version and commit.

This is not bookkeeping. It is the same principle the platform already applies to Evidence: a figure that cannot be traced to its inputs is not evidence, it is an assertion.

## Consequences

**Accepted costs**

- **`AggregationRequest` gains a field**, and `PatternSet` gains resolution provenance. Both are contract changes to a released package (`v1.2.0`). The new field defaults to empty, so behaviour with a single corpus is unchanged — but `schema_version` moves regardless, because the persisted shape changes.
- **A correct ERPNext population now requires supplying `frappe` as well.** The CLI must make this possible and must not make it silent: aggregating ERPNext without `frappe` should still work and still be honest about resolving 492 rather than 510.
- **[W3](../docs/evidence-platform/BACKLOG.md#w3--hrms-support) arrives sooner than planned.** `hrms` inherits from both `frappe` and `erpnext`, so it would need two supporting corpora, and the framework-versus-consumer question becomes harder to defer. This decision does not settle W3; it makes the mechanism W3 will need exist first, which is the right order.

**Preserved**

- **Extraction stays purely descriptive**, which is Extraction §5's whole point. A record says what a file says. The judgement "this is a `Document` subclass" is an inference, and inferences belong where they can be recomputed from stored inputs rather than baked into an artifact.
- **Extraction of one repository never requires another to be present.** Under Option 1 it would have, which would have made the extractor's output depend on the machine's checkout layout — the opposite of reproducible.
- **Existing behaviour is untouched.** `whitelisted_api_decoration` must return identical figures — 518/520 and 15/520 for `frappe`, 705/705 and 59/705 for `erpnext` — with every existing `pattern_id` unchanged. This is the regression check W5 already specifies.

**Rejected alternatives**

- **Option 1 (resolve at extraction).** Simpler downstream, but it puts an inference inside a record that claims to state a fact, and couples extraction of one repository to the presence of another.
- **Option 3 (resolve in isolation, declare the residue).** Consistent with how the platform handles what it cannot measure — but the platform *can* now measure this. Declaring a known 3.5% undercount is a different act from disclosing an unknown, and only the second is honesty.

## Notes

Two figures become stale when this is implemented and must be corrected together, not separately: the `blocker` text on the `CONTROLLER_LIFECYCLE_HOOK` entry in [`aggregation/population.py`](../aggregation/population.py) and [Aggregation §2.1](../docs/evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md), both of which cite a measured lower bound of 482 for ERPNext. The measured population is 510. The bound was correct and conservative; it is superseded, not wrong.
