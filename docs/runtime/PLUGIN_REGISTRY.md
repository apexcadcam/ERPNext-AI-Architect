# PLUGIN REGISTRY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md). How a [`MODULE_SYSTEM.md`](MODULE_SYSTEM.md)-compliant module actually gets found, activated, and validated at runtime.
**Scope:** Discovery, enable/disable, dependency validation, capability discovery. No code.

---

## 1. Discovery — No Hardcoded Imports

At boot ([`RUNTIME_BOOT_SEQUENCE.md § 2`](RUNTIME_BOOT_SEQUENCE.md#2-plugin-discovery)), the Registry enumerates a configured set of module locations (a directory convention, an installed-package manifest, or an explicit registry file each module contributes one entry to — the same manifest-based discovery [`CRAWLER_PLUGIN_SYSTEM.md § 2`](../crawler/CRAWLER_PLUGIN_SYSTEM.md#2-registration-not-modification) already established for connectors, one layer up) and reads each candidate's [`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest) manifest. **No file in the Runtime's own code ever names a module directly** — the discovery mechanism finds manifests; it never imports a concrete module by a hardcoded path or class reference, which is what makes "no runtime modification to add a module" true structurally rather than by convention.

## 2. Registration

A discovered module with a valid manifest is **registered** — added to the Registry's index, keyed by `module_id` — but not yet active. Registration is purely bookkeeping: it makes the module's declared `capabilities_provided`/`capabilities_required` visible to [§4](#4-dependency-validation) and [§5](#5-capability-discovery) without running any of the module's own code yet.

## 3. Enable / Disable

Every registered module has an explicit state, `enabled` or `disabled`, set by [`CONFIGURATION_SYSTEM.md`](CONFIGURATION_SYSTEM.md)'s module layer (defaulting to the manifest's own `enabled_by_default`). A `disabled` module is registered (its capabilities are known, for dependency-graph purposes) but never reaches `init()`/`start()` — this is what lets an operator turn off, say, the Embedding module in an environment that doesn't need it, without the Registry's dependency graph breaking for modules that don't actually require it at that moment (see [§4](#4-dependency-validation)'s handling of disabled-but-required capabilities).

## 4. Dependency Validation

Before any module reaches `init()`, the Registry builds the full capability graph across every **enabled** module and checks:

1. **Every `capabilities_required` is satisfied** by at least one enabled module's `capabilities_provided` — an unsatisfied requirement fails validation for the requiring module (and, transitively, anything that depends on it) rather than allowing it to start and fail unpredictably later.
2. **No dependency cycle exists** — enforced at validation time, the same "reject at write time, don't merely tolerate at read time" discipline already established for the Knowledge Graph's `depends_on` edges in [`KNOWLEDGE_GRAPH_SPEC.md § 3`](../knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md#3-relationship-vocabulary), applied here to the module dependency graph instead of the knowledge graph.
3. **A capability required by more than one enabled module is provided by exactly one of them** — ambiguous capability provision (two modules both claiming `document.persist`) fails validation rather than silently picking one, since a silent pick is exactly the kind of nondeterminism [`RUNTIME_ARCHITECTURE.md § 5`](RUNTIME_ARCHITECTURE.md#5-core-principles-and-where-each-is-addressed)'s "Deterministic" principle forbids.

A module failing any of these three checks is registered but never activated, and the failure is a boot-blocking error unless the module was explicitly marked optional in configuration — see [`RUNTIME_BOOT_SEQUENCE.md § 3`](RUNTIME_BOOT_SEQUENCE.md#3-dependency-validation).

## 5. Capability Discovery

At any point after registration, any module (via the Container, per [`DEPENDENCY_INJECTION.md`](DEPENDENCY_INJECTION.md)) or the CLI (per [`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md)'s `architect plugins list`) can query the Registry for "which enabled modules provide capability X" or "what does module Y provide/require" — this is what makes `architect doctor` (per [`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md)) able to report the full capability graph without re-deriving it, and what lets a future distributed deployment ask "which node currently hosts capability X" using the identical query shape, per [`RUNTIME_ARCHITECTURE.md § 7`](RUNTIME_ARCHITECTURE.md#7-non-functional-requirements-at-scale)'s "without redesign" requirement.

## 6. Scale

At hundreds of modules, discovery, registration, and dependency validation are each `O(modules + edges)` operations run once at boot (and again only when configuration explicitly requests a reload, per [`LIFECYCLE.md`](LIFECYCLE.md)) — never re-derived on every capability lookup, which instead reads the already-validated graph built once at [§4](#4-dependency-validation)'s completion.
