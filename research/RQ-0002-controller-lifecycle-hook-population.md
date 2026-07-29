# Controller Lifecycle Hook Population

## Status

- Date opened: 2026-07-29
- Date closed: 2026-07-29
- Status: `Resolved` — the empirical question is answered. One **design decision remains open** and is stated in [Open Questions](#open-questions); it is a decision for review, not an unfinished investigation.

**Changelog**
- 2026-07-29 — Opened and investigated (RQ-0002). Answers the question the Evidence Platform's own `SkippedAggregation` has been declaring since `v1.2.0`.

## Question

**What is the set of classes on which a Frappe `Document` lifecycle hook could possibly appear — and can that set be derived from a static AST walk of a repository's source alone?**

Sub-questions:

1. Is the population "`Document` subclasses" or "declared DocTypes"? They are not the same set.
2. Do abstract intermediate base classes belong in the population, or only concrete DocType controllers?
3. How deep do real inheritance chains go, and does a single-level base check suffice?
4. Are there controllers an AST cannot see — dynamic bases, metaclasses, runtime class creation?
5. Can a single repository's Evidence resolve its own population?

## Background

This is not a speculative question. The platform has been declaring it, in writing, in every `PatternSet` it produces since `v1.2.0`:

> Not derivable from persisted Evidence alone. The collector emits a record only when a hook is found, so classes without hooks leave no trace: the numerator exists but the population does not.

`controller_lifecycle_hook` is one of two Evidence categories and the only one that cannot be aggregated. **713 Evidence records** — 237 in `frappe`, 476 in `erpnext` — are collected and cannot be turned into a measurement. This question is the precondition for [W5](../docs/evidence-platform/BACKLOG.md#w5--sprint-22-denominator-work), and per the repository's own Stage 1 rule it is answered before anything is built.

## Existing Repository Check

- [`docs/evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md` §2.1](../docs/evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md) states the gap and gives a **lower bound** of 482 for ERPNext (448 direct plus "at least 34" via intermediate bases), explicitly noting that multi-level chains were unresolved at the time. This research supersedes that estimate with a measured figure.
- [`aggregation/population.py`](../aggregation/population.py) carries the same text as the executable `blocker` on the `POPULATION_BASES` entry.
- No Rule in `rules/` addresses controller inheritance.

## Method

A static AST walk of the real, pinned checkouts at `/home/gaber/frappe-bench/apps`, building a class-definition graph (`class name → declared base names`) and resolving `Document` descent transitively. Run three ways: each repository in isolation, both repositories as one combined graph, and against DocType JSON definitions for comparison.

**Tier 1 source only** — the framework and application source itself, which per [RESEARCH_FRAMEWORK.md §3](RESEARCH_FRAMEWORK.md#3-which-sources-are-considered-authoritative) is the highest-trust evidence available. No blog, forum, or documentation claim is relied on.

Versions measured: `frappe` v15.103.1, `erpnext` v15.102.0 — the same revisions the committed corpus describes.

## Findings

### F1 — The population is `Document` subclasses, resolved transitively

| | `frappe` | `erpnext` |
|---|---|---|
| Direct `class X(Document)` | 264 | 448 |
| Transitive, via intermediate bases | 11 | 62 |
| **Population** | **275** | **510** |
| DocType JSON definitions | 266 | 501 |

The measured ERPNext population is **510**, against the specification's recorded lower bound of 482. The bound was correct and conservative.

### F2 — DocType count is not the population, in either direction

`frappe` has 275 controllers against 266 DocType definitions; `erpnext` has 510 against 501. The sets differ **both ways**:

- Every DocType JSON does have a `.py` controller — measured, 0 exceptions in either repository.
- But not every `Document` subclass is a DocType. Abstract intermediates such as `AccountsController`, `StockController`, and `TransactionBase` are `Document` subclasses with no DocType of their own.

Counting DocType definitions would therefore be a different quantity wearing the population's name.

### F3 — Intermediate bases carry hooks, so they belong in the population

Measured directly:

| Class | Lifecycle hooks it defines |
|---|---|
| `AccountsController` | `validate`, `on_cancel`, `before_cancel`, `on_trash` |
| `StockController` | `validate` |
| `SellingController` | `validate` |
| `TransactionBase` | none |

A hook defined on `AccountsController` is real, runs for every descendant, and is already counted in the numerator by the existing collector. Excluding intermediates from the denominator while counting them in the numerator would inflate support. `TransactionBase` defining none is not a reason to exclude it — a class that *could* carry a hook and does not is exactly what a denominator is for.

### F4 — Chains reach depth 6; a single-level base check is not sufficient

Depth distribution of transitive controllers (0 = base is `Document` itself):

| Depth | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| `frappe` | 4 | 11 | — | — | — | — | — |
| `erpnext` | 3 | 7 | 9 | 8 | 6 | 7 | 7 |

Matching `class X(Document)` plus one level of known base names would miss 37 of ERPNext's 62 transitive controllers.

### F5 — Zero dynamic bases: the population **is** statically derivable

Across 3,800 parsed files and 1,938 class definitions, **not one class** has a base expression an AST cannot resolve to a name — no metaclass indirection, no runtime class construction, no computed bases in either repository.

This is the feasibility answer, and it is a clean yes: an AST-based collector can see the entire class graph.

### F6 — **Inheritance crosses repository boundaries, and this is decisive**

| Resolution strategy | `frappe` | `erpnext` |
|---|---|---|
| Repository in isolation | 275 | 492 |
| Combined `frappe` + `erpnext` graph | 275 | **510** |

**18 ERPNext controllers descend from `Document` only via a base class defined in `frappe`** — `NestedSet` (`frappe/utils/nestedset.py`, 14 subclasses) and `WebsiteGenerator` (`frappe/website/website_generator.py`, 2), among others.

Aggregating ERPNext's `EvidenceSet` in isolation would therefore undercount its own population by **3.5%**, silently. `frappe` shows 0 such cases, which is expected and structural: the framework has nothing upstream to inherit from. **The dependency is one-directional, and so is the error.**

### F7 — A naive "classes in doctype directories" count would be badly wrong

85 classes defined inside ERPNext's DocType controller files subclass `ValidationError`, not `Document` — they are exception types that happen to live beside the controller. Any collector keyed on file location rather than on resolved base classes would admit all 85.

## Evidence Summary

The population is derivable statically (F5), but **only from a class graph that spans every repository in the dependency chain** (F6). The single most important consequence is architectural rather than algorithmic: it is not a property of the collector, it is a property of what one `EvidenceSet` is allowed to contain.

Everything else is settled. The population is transitively-resolved `Document` subclasses including abstract intermediates (F1, F3), not DocType definitions (F2), resolved to full depth (F4), keyed on base classes rather than file location (F7).

## Open Questions

**One design decision, for review — this is what "approve the research" decides.**

Cross-repository resolution (F6) must be handled somehow. Three options, with the trade-off stated rather than a recommendation dressed as a finding:

1. **Resolve ancestry at extraction time.** Each class-definition Evidence record carries its resolved `is_document_subclass` verdict, computed while the extractor still has the tree in hand. Simple downstream — aggregation stays a pure count over one `EvidenceSet`. But the extractor would need `frappe` present to extract `erpnext`, which makes extraction of one repository depend on another and weakens "Evidence records what this file says".
2. **Aggregate over a set of `EvidenceSets`.** Record raw base names as Evidence; let aggregation resolve the graph across `frappe` + `erpnext` together. Keeps Evidence purely descriptive, which matches Extraction §5. But `AggregationRequest` currently takes exactly one `EvidenceSet`, so this is a contract change, and it reopens the framework-versus-consumer question in [W3](../docs/evidence-platform/BACKLOG.md#w3--hrms-support) immediately rather than later.
3. **Resolve within one repository and declare the residue.** Aggregate the 492 that resolve in isolation and emit a `SkippedAggregation`-style disclosure for the 18 that do not. Smallest change, and consistent with how this platform already handles what it cannot measure. But it knowingly ships a 3.5% undercount when the correct figure is now known — which is a different thing from not knowing it.

Option 2 is the one that matches the platform's existing principles most closely; option 3 is the one that ships soonest. **The decision is not mine to make here.**

## Final Recommendation

The `controller_lifecycle_hook` population **is** derivable, and Sprint 22 is viable. The new Evidence category should record **class definitions with their declared base classes** — raw names, atomically, one record per class — with descent resolved by a consumer rather than asserted by the collector, pending the decision above.

Two figures should be corrected when Sprint 22 lands: the `POPULATION_BASES` blocker text and the specification both cite a lower bound of 482 for ERPNext. The measured population is **510**.

## Potential Rule Candidates

None from this research. It answers a question about *this project's own measurement capability*, not about how an ERPNext developer should build something. A Rule about controller inheritance depth may become possible **after** the population exists and the hook-implementation rates can actually be measured — which is the point of Sprint 22.

## Related Topics

- [W5 — Sprint 22 denominator work](../docs/evidence-platform/BACKLOG.md#w5--sprint-22-denominator-work)
- [W3 — HRMS support](../docs/evidence-platform/BACKLOG.md#w3--hrms-support) — F6 makes this more urgent: `hrms` inherits from both `frappe` and `erpnext`, so its population would be unresolvable in isolation by a wider margin than ERPNext's
- [Pattern Aggregation Specification §2.1](../docs/evidence-platform/PATTERN_AGGREGATION_SPECIFICATION.md) — the gap this research closes

## References

Tier 1, measured directly at the pinned revisions:

- `frappe` v15.103.1 — 1,384 parsed files, 926 class definitions
- `erpnext` v15.102.0 — 2,416 parsed files, 1,012 class definitions
- `frappe/frappe/model/document.py` — `Document`, the root of the population
- `frappe/frappe/utils/nestedset.py` — `NestedSet`, 14 ERPNext subclasses
- `frappe/frappe/website/website_generator.py` — `WebsiteGenerator`, 2 ERPNext subclasses
- `erpnext/erpnext/controllers/` — `AccountsController`, `StockController`, `SellingController`, `BuyingController`, `SubcontractingController`, `TransactionBase`, `StatusUpdater`
