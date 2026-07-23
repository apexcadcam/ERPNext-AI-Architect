# DEPENDENCY INJECTION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md). How a module obtains what [`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest)'s `capabilities_required` declares, once [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation) has confirmed it's satisfiable.
**Scope:** The Runtime Container's resolution model. No code.

---

## 1. The One Rule

**Modules never instantiate each other.** A module that needs storage access, event publishing, or another module's capability receives it as an argument to `init(container)` ([`MODULE_SYSTEM.md § 3`](MODULE_SYSTEM.md#3-the-module-lifecycle-interface)) — it asks the Container for a capability by name and receives whatever currently satisfies it. A module holding a direct reference to another module's concrete implementation, obtained any way other than through the Container, is out of contract, exactly as [`CRAWLER_PLUGIN_SYSTEM.md § 4`](../crawler/CRAWLER_PLUGIN_SYSTEM.md#4-what-a-new-connector-must-never-do) already forbade one connector reaching into another's state — the same rule, one layer up.

## 2. Resolution by Capability, Not by Type

The Container resolves `capabilities_required: [document.persist]` to *whichever enabled module* [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation) confirmed provides `document.persist` — never to a hardcoded module name. This is what lets a future second Storage-backed module, or a test double (see [§4](#4-test-doubles)), satisfy the exact same dependency with zero change to the requesting module's own code, and it is the direct mechanism behind [`RUNTIME_ARCHITECTURE.md § 1`](RUNTIME_ARCHITECTURE.md#1-the-one-rule-everything-else-follows)'s "the Runtime knows modules, not domains" — the Container doesn't know *what* `document.persist` does either, only that something registered to provide it.

## 3. Resolution Timing and Scope

| Scope | Resolved | Lifetime |
|---|---|---|
| **Singleton** | Once, at [`RUNTIME_BOOT_SEQUENCE.md § 4`](RUNTIME_BOOT_SEQUENCE.md#4-configuration-loading)'s module initialization | Runtime process lifetime — most modules (Crawler, Validator, Rule Engine) are singletons |
| **Pipeline-run-scoped** | Once per [`PIPELINE_ENGINE.md`](PIPELINE_ENGINE.md) run, freshly | One pipeline execution — used for anything that must not leak state between two concurrent runs of the same pipeline (e.g., a per-run correlation context) |
| **Request-scoped** | Once per CLI invocation or external API call | One command's execution, per [`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md) |

A module declares which scope it needs for each dependency in its manifest; the Container is responsible for tearing down scoped instances at the end of their scope's lifetime, never leaking a pipeline-run-scoped instance into the next run.

## 4. Test Doubles

Because resolution is always by capability, a test can register a minimal double satisfying `document.persist` (writing to an in-memory structure instead of real storage) and hand it to the Container in place of the real Storage module — no module under test needs to know or care whether it received the real implementation or a test double, since both satisfy the identical capability contract. This is what makes [`docs/crawler/TESTING_STRATEGY.md`](../crawler/TESTING_STRATEGY.md)'s fixture-based, no-live-network testing discipline extend cleanly to every module in the Runtime, not just the Crawler — the Container is the seam that makes substitution possible everywhere, uniformly.

## 5. Failure Mode

A module whose declared dependency cannot be resolved never reaches `init()` at all — this was already caught at [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation)'s boot-time validation, so the Container's resolution step, by the time it runs, is a lookup against an already-proven-satisfiable graph, never a point where a missing dependency is discovered for the first time. Resolution failing at this stage despite passing validation is treated as a Runtime defect (the graph and the actual resolution disagree), not a configuration problem.
