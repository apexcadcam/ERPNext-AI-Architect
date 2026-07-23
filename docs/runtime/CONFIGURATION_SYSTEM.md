# CONFIGURATION SYSTEM

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md § 4.4](RUNTIME_ARCHITECTURE.md#44-source_connector_specmds-ten-declarations-and-hierarchical-configuration).
**Scope:** Hierarchical configuration — six layers, inheritance, validation, versioning. No code.

---

## 1. Configuration Is Data, Read Once Per Boot (or Explicit Reload)

Every module's behavior is parameterized by configuration resolved through this system — never by a module reading an environment variable or a file directly on its own. This keeps [`PLUGIN_REGISTRY.md § 3`](PLUGIN_REGISTRY.md#3-enable--disable) (enable/disable), retry/rate-limit tuning ([`docs/crawler/RATE_LIMITING.md`](../crawler/RATE_LIMITING.md), [`RETRY_POLICY.md`](../crawler/RETRY_POLICY.md)), and every other tunable in this document set governed by one visible, auditable mechanism instead of scattered ad hoc reads.

## 2. The Six Layers

Precedence lowest → highest — a more specific layer overrides a less specific one *for the specific keys it sets*, never wholesale replacing the less specific layer's other keys:

1. **Runtime defaults** — built-in, safe fallback values shipped with the Runtime itself; every key has one, so a completely empty configuration still boots to a conservative, working state.
2. **Global** — repository/organization-wide settings (e.g., the default politeness delay every connector inherits unless overridden).
3. **Environment** — `dev` / `staging` / `production`-style overrides (e.g., a lower rate-limit ceiling in `dev` to avoid burning a shared API quota during testing).
4. **Module** — a specific module's own settings, populated from that module's `config_schema_ref` ([`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest)).
5. **Pipeline** — a specific Pipeline Definition's run parameters (per [`PIPELINE_ENGINE.md § 1`](PIPELINE_ENGINE.md#1-a-pipeline-definition-is-data-not-code)), e.g., which stages are included for this run.
6. **Connector** — the most specific layer; a single [`Source Connector`](../crawler/SOURCE_CONNECTOR_SPEC.md)'s own ten declarations, already fully specified by that document and simply hosted at this layer, not redefined by it.

## 3. Inheritance

A key not set at a given layer falls through to the next-less-specific layer, down to Runtime defaults — resolution never fails with "key not found" for any key the schema declares, only for a key the schema itself never declared (a true configuration error, distinct from "unset, use the default"). Two sibling keys at the same layer (e.g., two different connectors) never inherit from each other — inheritance is strictly vertical through the six layers, never lateral.

## 4. Validation

Every layer's values are checked against the owning entity's declared schema (a module's `config_schema_ref`, a connector's [`SOURCE_CONNECTOR_SPEC.md § 1`](../crawler/SOURCE_CONNECTOR_SPEC.md#1-the-ten-required-declarations)) at [`RUNTIME_BOOT_SEQUENCE.md § 4`](RUNTIME_BOOT_SEQUENCE.md#4-configuration-loading) — before any module reaches `init()`, exactly as [`SOURCE_CONNECTOR_SPEC.md § 3`](../crawler/SOURCE_CONNECTOR_SPEC.md#3-contract-compliance) already required for connectors specifically, now generalized to every layer. A schema violation at any layer is a boot-blocking error, never a warning silently tolerated — this is what `architect config validate` ([`CLI_ARCHITECTURE.md`](CLI_ARCHITECTURE.md)) checks without actually booting the Runtime.

## 5. Versioning

The configuration schema itself carries a version, per the same discipline [`docs/ai-retrieval/METADATA_SCHEMA.yaml`](../ai-retrieval/METADATA_SCHEMA.yaml)'s `schema_version` and [`docs/crawler/VERSIONING_POLICY.md § 2`](../crawler/VERSIONING_POLICY.md#2-compatibility-rule)'s Crawl Item schema compatibility rule already established — a MAJOR schema bump requires every layer's stored configuration to be explicitly migrated or re-validated, never silently reinterpreted under a new meaning. A configuration *value* change (not a schema change) is itself an auditable event — published to the [Event Bus](EVENT_BUS.md) as a `ConfigurationChanged` event, carrying which layer and key changed, giving configuration drift the same traceability this project already demands of every knowledge artifact.

## 6. What Configuration Never Holds

Per [`SOURCE_CONNECTOR_SPEC.md § 1.2`](../crawler/SOURCE_CONNECTOR_SPEC.md#12-authentication)'s existing rule, extended to every layer: no literal credential value is ever stored in configuration, at any layer — only a `credential_reference` pointing to where one is resolved. This is a hard validation rule at [§4](#4-validation), not a convention: a configuration value that looks like a credential (matching common secret-shape heuristics) fails validation outright rather than being accepted and logged, per [`LOGGING_AND_OBSERVABILITY.md § 1`](LOGGING_AND_OBSERVABILITY.md#1-structured-logging)'s "never log a literal secret" rule applied one step earlier, at the point of entry.
