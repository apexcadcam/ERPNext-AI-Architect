# RUNTIME BOOT SEQUENCE

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md). Ties together every mechanism the other eleven documents define, in the order they actually run.
**Scope:** What happens between `architect runtime start` and `Ready`. No code.

---

## 0. Overview

```
1. Runtime Startup
2. Plugin Discovery
3. Dependency Validation
4. Configuration Loading
5. Pipeline Registration
6. Connector Registration
7. Health Checks
8. Ready State
```

Every step is a hard gate — a failure at step N halts the sequence at N; the Runtime never proceeds to `Ready` on a partial or best-effort boot, per [`RUNTIME_ARCHITECTURE.md § 5`](RUNTIME_ARCHITECTURE.md#5-core-principles-and-where-each-is-addressed)'s "Deterministic" principle. Each step below corresponds one-to-one to a [`LIFECYCLE.md § 1`](LIFECYCLE.md#1-runtime-process-states) state.

---

## 1. Runtime Startup

The process starts, the [Dependency Injection Container](DEPENDENCY_INJECTION.md) is constructed empty, and the [Event Bus](EVENT_BUS.md) begins accepting registrations (though no module exists yet to publish or subscribe to anything). No module code runs at this step — it is infrastructure-only, standing up the substrate everything else registers into.

## 2. Plugin Discovery

The [Plugin Registry](PLUGIN_REGISTRY.md#1-discovery--no-hardcoded-imports) enumerates configured module locations and reads every candidate's [`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest) manifest, registering each — per [`PLUGIN_REGISTRY.md § 2`](PLUGIN_REGISTRY.md#2-registration). No module's `init()` runs yet. A manifest that fails to parse at all is a boot-blocking error (a malformed manifest cannot be safely defaulted to "disabled" — its intended enabled/disabled state is itself unknown).

## 3. Dependency Validation

The full capability graph across every module marked `enabled` (from manifest defaults, pending [Step 4](#4-configuration-loading)'s override) is checked per [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation): every requirement satisfiable, no cycles, no ambiguous capability provision. **This runs before configuration loading** because a module's *declared* dependencies (from its manifest) are what's being checked here — configuration can change *which modules are enabled*, but a disabled module's manifest is still read and its declared shape still contributes to graph-shape validation, so structural problems (a cycle, an ambiguous provider) are caught even before configuration is known to be otherwise valid.

## 4. Configuration Loading

[`CONFIGURATION_SYSTEM.md`](CONFIGURATION_SYSTEM.md)'s six layers are resolved and validated, per [`CONFIGURATION_SYSTEM.md § 4`](CONFIGURATION_SYSTEM.md#4-validation) — this is also where the Module layer's `enabled`/`disabled` overrides ([`PLUGIN_REGISTRY.md § 3`](PLUGIN_REGISTRY.md#3-enable--disable)) are actually applied, which may narrow the set of modules that proceed past this point relative to what Step 3 validated structurally. A configuration schema violation at any layer halts the boot here — `architect config validate` ([`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md)) runs exactly this step in isolation, without proceeding further, which is how it diagnoses configuration problems without a full Runtime start.

## 5. Pipeline Registration

Every configured [Pipeline Definition](PIPELINE_ENGINE.md#1-a-pipeline-definition-is-data-not-code) is resolved against the now-final set of enabled, validated, configured modules — binding each declared stage to the module capability that implements it, and wiring the [Event Bus](EVENT_BUS.md#2-publish--subscribe) subscriptions/publications every module's manifest declared. A Pipeline Definition referencing a stage no enabled module actually provides fails registration — caught here, not at first run.

## 6. Connector Registration

Nested one level inside Step 5, specifically for the Crawler module (if enabled): once the Crawler module itself is registered and configured, it runs its **own** internal registration pass over [`Source Connectors`](../crawler/SOURCE_CONNECTOR_SPEC.md), per [`CRAWLER_PLUGIN_SYSTEM.md § 2`](../crawler/CRAWLER_PLUGIN_SYSTEM.md#2-registration-not-modification) — unchanged, and invisible to the Runtime's own Plugin Registry, which only ever sees one entry: "the Crawler module." This is the fractal nesting [`MODULE_SYSTEM.md § 1`](MODULE_SYSTEM.md#1-a-module-is-a-declaration-not-an-assumption) already noted: the same registration discipline recurring one level down, inside a module that happens to host its own plugin system.

## 7. Health Checks

Every module past registration runs `init()` then `start()` ([`MODULE_SYSTEM.md § 3`](MODULE_SYSTEM.md#3-the-module-lifecycle-interface)), then its `health_check()` is invoked once, per [`LOGGING_AND_OBSERVABILITY.md § 4`](LOGGING_AND_OBSERVABILITY.md#4-health-checks) — a module reporting unhealthy here is a boot-blocking failure **unless** it was explicitly marked optional in configuration (per [`RUNTIME_ARCHITECTURE.md § 4.4`](RUNTIME_ARCHITECTURE.md#44-source_connector_specmds-ten-declarations-and-hierarchical-configuration)-style connector-level granularity applying equally at the module level: an operator may choose to boot without a non-critical module rather than block entirely on it).

## 8. Ready State

Reached only after all seven prior steps complete without a boot-blocking failure. The Runtime transitions to `Running` ([`LIFECYCLE.md § 1`](LIFECYCLE.md#1-runtime-process-states)), begins accepting CLI commands and external triggers, and every module's `start()`-established subscriptions become live — the first event any module publishes after this point is the first moment any real work (a crawl, a validation pass) can actually happen. `architect runtime start` blocks until this state is reached (or a boot-blocking failure is reported) and exits non-zero on failure, per [`CLI_ARCHITECTURE.md § 5`](CLI_ARCHITECTURE.md#5-exit-codes-reflect-the-same-categories-error_handlingmd-already-defines).

---

## 9. Restart vs. Cold Boot

A module-level restart (per [`LIFECYCLE.md § 2`](LIFECYCLE.md#2-module-states)) re-enters at that module's own `Initialized` state and does not re-run Steps 1–3 for the whole Runtime — only a full process restart runs this entire sequence from Step 1. This distinction is what makes [`RUNTIME_ARCHITECTURE.md § 7`](RUNTIME_ARCHITECTURE.md#7-non-functional-requirements-at-scale)'s "hundreds of plugins" tractable operationally: recovering one failed module never requires re-validating every other module's already-proven-good state.
