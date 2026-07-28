# CLI ARCHITECTURE

**Status:** Foundational — the design below is implemented in part; see the note that follows.
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md).
**Scope:** The unified `architect` command surface — a client of the Runtime, not a privileged backdoor into it.

---

## 0. What is actually implemented

This document is the original design. It is left as written; the table in §2 describes the intended surface, not the current one. The commands that exist today, in [`runtime/cli.py`](../../runtime/cli.py):

| Command | Added by |
|---|---|
| `architect doctor`, `plugins list`, `runtime info`, `config validate` | Sprint 1 — as designed below |
| `architect run-goal` | Sprint 14 (ADR-005), a disclosed additive exception to the Runtime freeze |
| `architect evidence extract`, `patterns aggregate`, `patterns report` | The Evidence Platform — specified in [`docs/evidence-platform/CLI_SPECIFICATION.md`](../evidence-platform/CLI_SPECIFICATION.md) |

`crawl`, `pipeline run`, `graph build`, `validate`, and `runtime start` remain unimplemented.

§4's rule — structured output first, human-readable second, never two divergent code paths — is now enforced structurally rather than by convention: every Evidence Platform command builds one frozen `runtime.output.CommandOutput` and both renderers read from it.

---

## 1. The CLI Is a Consumer, Not a Special Case

Every `architect` command resolves to exactly one of: a Runtime lifecycle operation, a [`PLUGIN_REGISTRY.md`](PLUGIN_REGISTRY.md) query, or a [`PIPELINE_ENGINE.md`](PIPELINE_ENGINE.md) run — invoked through the same Dependency Injection Container and Event Bus any module uses, request-scoped per [`DEPENDENCY_INJECTION.md § 3`](DEPENDENCY_INJECTION.md#3-resolution-timing-and-scope). The CLI has no capability a module couldn't also have; it never reaches around [`MODULE_SYSTEM.md`](MODULE_SYSTEM.md)'s contract to touch a module's internals directly.

## 2. Command Structure

`architect <noun> <verb> [target] [--flags]` — nouns correspond to Runtime concepts, never to ERPNext-domain concepts (per [`RUNTIME_ARCHITECTURE.md § 1`](RUNTIME_ARCHITECTURE.md#1-the-one-rule-everything-else-follows), the CLI's own vocabulary is subject to the same "knows modules, not domains" boundary).

| Command | Noun | Resolves to |
|---|---|---|
| `architect runtime start` | `runtime` | [`RUNTIME_BOOT_SEQUENCE.md`](RUNTIME_BOOT_SEQUENCE.md), full sequence |
| `architect crawl frappe_docs` | `crawl` (sugar for `pipeline run crawler.acquisition --connector frappe_docs`) | [`PIPELINE_ENGINE.md § 4`](PIPELINE_ENGINE.md#4-existing-pipelines-as-pipeline-definitions)'s `crawler.acquisition` definition, scoped to one connector |
| `architect pipeline run acquisition` | `pipeline` | A named [Pipeline Definition](PIPELINE_ENGINE.md#1-a-pipeline-definition-is-data-not-code) run, unscoped (every enabled connector) |
| `architect plugins list` | `plugins` | [`PLUGIN_REGISTRY.md § 5`](PLUGIN_REGISTRY.md#5-capability-discovery), formatted for a terminal |
| `architect graph build` | `graph` | The `knowledge.graph_build` Pipeline Definition |
| `architect validate` | `validate` | The `knowledge.validation` Pipeline Definition, run standalone against already-persisted, not-yet-validated documents |
| `architect doctor` | `doctor` | [`LOGGING_AND_OBSERVABILITY.md § 4`](LOGGING_AND_OBSERVABILITY.md#4-health-checks) across every registered module, in one pass |
| `architect config validate` | `config` | [`CONFIGURATION_SYSTEM.md § 4`](CONFIGURATION_SYSTEM.md#4-validation), without booting the Runtime |

## 3. No Command Bypasses Validation

`architect crawl <connector>` cannot be pointed at a connector that failed [`PLUGIN_REGISTRY.md § 4`](PLUGIN_REGISTRY.md#4-dependency-validation)'s dependency validation, or that [`SOURCE_CONNECTOR_SPEC.md § 3`](../crawler/SOURCE_CONNECTOR_SPEC.md#3-contract-compliance) never accepted as contract-compliant — the CLI surfaces the same validation failure a programmatic caller would get, never a "force anyway" flag that lets a human route around a check a module would otherwise enforce. `--force`-shaped flags, where they exist at all, apply only to genuinely operator-judgment decisions (e.g., re-running an already-completed pipeline run intentionally) never to skipping a contract or schema check.

## 4. Output Is Structured First, Human-Readable Second

Every command's underlying result is the same structured object [`LOGGING_AND_OBSERVABILITY.md`](LOGGING_AND_OBSERVABILITY.md) would log — a terminal-friendly rendering is a presentation choice layered on top (a `--json` flag returns the same structure a script would consume), never a separate, differently-shaped code path that could drift from what actually happened.

## 5. Exit Codes Reflect the Same Categories `ERROR_HANDLING.md` Already Defines

A CLI invocation exits `0` only on genuine success; a `Recoverable`-category failure that exhausted its retries, a `Permanent`-category failure, and an `Authentication`-category failure ([`docs/crawler/ERROR_HANDLING.md`](../crawler/ERROR_HANDLING.md)) map to distinct, documented non-zero exit codes — so a script invoking `architect crawl` can distinguish "the source is genuinely gone" from "try again later" without parsing log text, reusing the categorization already frozen rather than inventing a second one for the CLI specifically.

## 6. Future Growth

New modules register new capabilities, not new top-level nouns by default — a future `Rule Engine` module surfaces as `architect rule evaluate <proposal>` by declaring that command binding in its own manifest ([`MODULE_SYSTEM.md § 2`](MODULE_SYSTEM.md#2-the-module-manifest) extended with an optional `cli_bindings` field), never by editing the CLI's own dispatch logic — the same "registration, not modification" discipline [`CRAWLER_PLUGIN_SYSTEM.md § 2`](../crawler/CRAWLER_PLUGIN_SYSTEM.md#2-registration-not-modification) established, applied here to command surface instead of pipeline stages.
