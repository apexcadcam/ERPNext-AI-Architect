# SPRINT 3 ARCHITECTURE PACKAGE — Integration Layer & Knowledge Graph v1

**Status:** Proposed — Architecture Only, Not Implemented. Awaiting approval.
**Authority:** Subordinate to [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md), [`ENGINEERING_META_MODEL.md`](ENGINEERING_META_MODEL.md), [`docs/runtime/RUNTIME_ARCHITECTURE.md`](docs/runtime/RUNTIME_ARCHITECTURE.md), and [`docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md`](docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md). None of these are redesigned here — this package extends them, per this project's standing "document integration points, never silently redesign frozen architecture" discipline.
**Scope:** The Integration Layer (Plugin System, Connector Layer, Secrets Management, Plugin Discovery, Security Boundaries) and Knowledge Graph v1 (traversal interfaces and the storage/materialization layer `KNOWLEDGE_GRAPH_SPEC.md § 5` explicitly deferred). No implementation. No Python. No pseudo-code. No class skeletons.
**Frozen and unmodified by this package:** Sprint 1 (`v0.1.0-runtime-bootstrap`) and Sprint 2 (`v0.2.0-knowledge-factory`) — every file under `runtime/`, `knowledge/`, `plugins/`; every document under `docs/runtime/`, `docs/knowledge-pipeline/`, `docs/crawler/`, `docs/ai-retrieval/`, `docs/studio/`; `ENGINEERING_META_MODEL.md`'s Knowledge Artifact Catalog; ADR-0001; ADR-0002.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Directory Structure](#3-directory-structure)
4. [Component Diagram](#4-component-diagram)
5. [Plugin Architecture](#5-plugin-architecture)
6. [Connector Architecture](#6-connector-architecture)
7. [Knowledge Graph Architecture](#7-knowledge-graph-architecture)
8. [Secrets Architecture](#8-secrets-architecture)
9. [Configuration Architecture](#9-configuration-architecture)
10. [Data Flow](#10-data-flow)
11. [Sequence Diagrams](#11-sequence-diagrams)
12. [Extension Points](#12-extension-points)
13. [Failure Scenarios](#13-failure-scenarios)
14. [Security Considerations](#14-security-considerations)
15. [Architectural Decisions (ADRs)](#15-architectural-decisions-adrs)
16. [Risks](#16-risks)
17. [Future Work](#17-future-work)
18. [Migration Strategy](#18-migration-strategy)

---

## 1. Executive Summary

Sprint 3 designs two things, and builds neither:

1. **The Integration Layer** — how the AI Architect talks to *live* external systems (ERPNext, MCP servers, GitHub, Docker, PostgreSQL, the filesystem, Playwright, and whatever comes after) without the part of the system that *decides what to do* ever knowing which live system, or which protocol, is actually being used.
2. **Knowledge Graph v1** — the traversal and storage architecture `docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md` already specified the *shape* of (nodes, edges, relationship vocabulary) and explicitly deferred the *mechanics* of ("node/edge storage and traversal are an implementation concern deferred entirely," `KNOWLEDGE_GRAPH_SPEC.md § 5`). Sprint 3 is that deferred mechanics layer, and nothing else — no new node type, no new relationship, no new artifact.

**Nothing here is a redesign.** Every major decision in this package is a generalization of a pattern this project already committed to once:

| Sprint 3 concept | Already-frozen pattern it generalizes | Where |
|---|---|---|
| Integration module hosting nested Connectors | Crawler module hosting nested Source Connectors | `docs/crawler/CRAWLER_PLUGIN_SYSTEM.md` |
| Connector Contract | Source Connector's ten required declarations | `docs/crawler/SOURCE_CONNECTOR_SPEC.md` |
| Secrets Resolver | `credential_reference` indirection (already forbids literal secrets in configuration) | `docs/runtime/CONFIGURATION_SYSTEM.md § 6` |
| Profile | The existing "Environment" configuration layer, generalized from `{dev, staging, production}` to any named profile | `docs/runtime/CONFIGURATION_SYSTEM.md § 2` |
| Graph Store Adapter | Storage Adapter (backend-agnostic, namespace-addressed, configuration-selected) | `docs/runtime/STORAGE_ABSTRACTION.md` |
| Capability-scoped connector resolution | "Resolve by capability, not by type" | `docs/runtime/DEPENDENCY_INJECTION.md § 2` |
| Planning/Execution boundary | MCP "only executes Tools; holds no architectural judgment of its own" | `ENGINEERING_META_MODEL.md` entries 20–21 |

**What Sprint 3 genuinely adds**, additively, to the frozen corpus:
- One new Runtime-level module family: **Integration** (peer to Crawler, Extractor, Validator).
- One new Runtime-level module family: **Knowledge Graph** (peer to the above; consumes Sprint 2's already-shipped artifact `relationships`/`dependencies` fields — no schema change to `knowledge/artifacts/`).
- One new Runtime-level capability: the **Secrets Resolver** (a sibling to the Storage Adapter, not a replacement for anything).
- A small, explicit widening of `RUNTIME_BOOT_SEQUENCE.md § 6` ("Connector Registration") from "specifically for the Crawler module" to "the Crawler module, and, if enabled, the Integration module, via the identical nested-registration mechanism" — see [§15, ADR-0003](#15-architectural-decisions-adrs).
- A small, explicit additive entry to `ENGINEERING_META_MODEL.md`'s Repository Folder Mapping, reserving `integration/` and `docs/integration/`, using the exact same "reserved, not yet created" courtesy already extended to `runtime/`, `crawler/`, and `studio/`.

**What Sprint 3 explicitly does not do:** implement anything; choose a Secrets backend or a Graph Store backend; build an Agent/Planner runtime (that remains `ENGINEERING_META_MODEL.md` entries 14–15, unbuilt); change `SOURCE_CONNECTOR_SPEC.md`, `KNOWLEDGE_GRAPH_SPEC.md`'s node/edge model, or any Sprint 1/2 code.

---

## 2. Architecture Overview

The system this project is building has, after Sprint 2, two halves: a **Runtime** (Sprint 1 — modules, plugins, pipelines, events, configuration) and a **Knowledge Factory** (Sprint 2 — artifacts, extraction, validation, conflict resolution) that turns raw material into trusted, versioned facts. Neither half, so far, can *act* on anything, and neither half can *connect its own facts together*. Sprint 3 closes both gaps, symmetrically:

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                      RUNTIME  (Sprint 1)                  │
                    │   Container · Plugin Registry · Event Bus · Pipeline      │
                    │   Engine · Configuration System · Storage Abstraction     │
                    └───────────┬─────────────────────────────┬─────────────────┘
                                │                               │
              ┌─────────────────┴──────────────┐   ┌────────────┴─────────────────┐
              │      KNOWLEDGE FACTORY           │   │      INTEGRATION LAYER        │
              │      (Sprint 2, frozen)          │   │      (Sprint 3, new)          │
              │                                   │   │                                │
              │  Extractor → Pattern Extraction   │   │  Integration module            │
              │  → Conflict Resolution            │   │  hosts nested Connectors:      │
              │  → Validator (8 gates)            │   │  ERPNext · MCP · GitHub ·      │
              │                                   │   │  Docker · PostgreSQL ·         │
              │  produces: ContentArtifact         │   │  Filesystem · Playwright        │
              │  (KnowledgeAPI, Pattern, ...)      │   │                                │
              └───────────────┬───────────────────┘   └───────────────┬────────────────┘
                                │ relationships/                        │ credential_reference
                                │ dependencies fields                    │ (never a literal secret)
                                ▼                                       ▼
              ┌───────────────────────────────────┐   ┌────────────────────────────────┐
              │   KNOWLEDGE GRAPH  (Sprint 3, new)  │   │   SECRETS RESOLVER (Sprint 3, new)│
              │   Graph Build Engine                │   │   env:// · dotenv:// ·          │
              │   Graph Store Adapter (interface)    │   │   profile:// · vault:// (future)  │
              │   Bounded-depth traversal            │   └────────────────────────────────┘
              └───────────────────────────────────┘
```

The Knowledge Factory and the Integration Layer are **peers, not a pipeline into one another**. A live Connector's output is operational (talking to one customer's live site right now) and is never silently absorbed into the Knowledge Graph's trusted, versioned facts — see [§15, ADR-0007](#15-architectural-decisions-adrs) and [§14](#14-security-considerations). The Knowledge Graph is built exclusively from artifacts that already passed Sprint 2's eight validation gates.

The thread that ties both halves together, conceptually, is the **Planning / Execution boundary** the Meta-Model already drew between `Skill`/`Agent` (entries 14–15 — decide *what* to do) and `MCP`/`Tool` (entries 20–21 — mechanically execute, hold no judgment). Sprint 3's Connector is the Runtime-layer implementation *behind* an `MCP` `Tool` the moment that Tool is actually invoked — the knowledge layer says a Tool exists and what it does in principle; the Integration Layer is how it actually happens against a real system. See [§6.4](#64-relationship-to-mcp--tool-meta-model-entries-2021).

---

## 3. Directory Structure

Two structures: the **code** reservation (mirroring how `runtime/`, `crawler/`, and `studio/` are already reserved-but-empty top-level folders per `ENGINEERING_META_MODEL.md`'s Repository Folder Mapping) and the **docs** family this package would eventually split into upon approval (mirroring `docs/crawler/`, `docs/knowledge-pipeline/`, `docs/runtime/`, `docs/studio/`).

### 3.1 Code Reservation (additive to `ENGINEERING_META_MODEL.md`'s Repository Folder Mapping)

```
integration/                       # Reserved, not yet created — Connector plugin code
    core/                          # shared connector lifecycle host, nested registry,
                                    # capability registration glue — never edited to add a connector
    connectors/
        erpnext/                   # one connector: ERPNext site (REST/RPC)
        mcp/                       # one connector: generic MCP server bridge
        github/                    # one connector: GitHub API
        docker/                    # one connector: Docker Engine API
        postgresql/                # one connector: PostgreSQL wire protocol
        filesystem/                # one connector: local/mounted filesystem
        playwright/                # one connector: browser automation
        <new_connector>/           # adding connector #8 looks exactly like adding connector #1

secrets/                           # Reserved, not yet created — Secrets Resolver backend
                                    # implementations only; never a place literal secrets live
                                    # in the repository (see §8)

knowledge/graph/                   # Reserved, not yet created — sibling to knowledge/artifacts,
                                    # knowledge/conflict, knowledge/validation, knowledge/extraction,
                                    # knowledge/pipelines. Graph Build Engine + Graph Store Adapter
                                    # interface. No new artifact schema — operates on
                                    # knowledge/artifacts/ ContentArtifact.relationships /
                                    # .dependencies fields exactly as Sprint 2 already defined them.
```

`.secrets/`, `profiles/*.secrets`, and any `.env` file are **never** reserved as repository paths — they are explicitly `.gitignore`d, operator-local, and named in [§8](#8-secrets-architecture) only as a *convention*, never as a folder this project's own repository owns or ships content into.

### 3.2 Documentation Family (proposed post-approval split)

Upon approval, this single package's content would be split the same way the original Runtime Architecture design was split into twelve documents — proposed names only, not created by this package:

```
docs/integration/
    INTEGRATION_ARCHITECTURE.md       # entry point — mirrors RUNTIME_ARCHITECTURE.md's role
    CONNECTOR_PLUGIN_SYSTEM.md        # mirrors CRAWLER_PLUGIN_SYSTEM.md
    CONNECTOR_SPEC.md                 # mirrors SOURCE_CONNECTOR_SPEC.md
    SECRETS_MANAGEMENT.md             # §8 of this package
    SECURITY_BOUNDARIES.md            # §14 of this package
    CONNECTOR_TESTING_STRATEGY.md     # mirrors docs/crawler/TESTING_STRATEGY.md

docs/knowledge-pipeline/
    KNOWLEDGE_GRAPH_ENGINE.md         # §7 of this package — subordinate to the existing,
                                       # unmodified KNOWLEDGE_GRAPH_SPEC.md
```

---

## 4. Component Diagram

```
                                   ┌───────────────────────────┐
                                   │      architect  (CLI)       │
                                   └──────────────┬────────────┘
                                                  │
                                   ┌──────────────▼────────────┐
                                   │      Runtime Core (S1)      │
                                   │  Container · Registry ·     │
                                   │  Event Bus · Pipeline Engine│
                                   │  Configuration · Storage    │
                                   │  Secrets Resolver  (S3, new)│
                                   └──┬─────────┬─────────┬─────┘
                    ┌──────────────────┘         │         └──────────────────┐
                    ▼                            ▼                            ▼
          ┌─────────────────┐         ┌─────────────────────┐      ┌─────────────────────┐
          │  Extractor (S2)  │         │   Validator (S2)      │      │  Integration (S3, new)│
          │  Pattern Extract  │         │   8 gates              │      │  hosts nested          │
          │  Conflict Resolve │         │                        │      │  Connector registry     │
          └────────┬─────────┘         └───────────┬────────────┘      └──────────┬─────────────┘
                    │  ContentArtifact                │  ValidatedArtifact          │
                    └───────────────┬─────────────────┘                            │
                                    ▼                                              ▼
                       ┌─────────────────────────┐                 ┌─────────────────────────────┐
                       │  Knowledge Graph (S3, new) │                 │   Connectors (nested plugins)  │
                       │  Graph Build Engine         │                 │  erpnext · mcp · github ·      │
                       │  Graph Store Adapter          │                 │  docker · postgresql ·          │
                       │  (interface only)              │                 │  filesystem · playwright          │
                       └─────────────────────────┘                 └──────────────┬───────────────┘
                                                                                    │ credential_reference
                                                                                    ▼
                                                                     ┌─────────────────────────┐
                                                                     │   Secrets Resolver backends │
                                                                     │   env · dotenv · profile ·    │
                                                                     │   vault (future)                │
                                                                     └─────────────────────────┘
```

Not built by Sprint 3, shown only as existing context: `Agents` module and `Rule Engine` module (both named, both unbuilt, per `docs/runtime/RUNTIME_ARCHITECTURE.md §§ 4.6–4.7`) are the eventual *callers* of a Connector, via `MCP`/`Tool` (`ENGINEERING_META_MODEL.md` entries 20–21) — Sprint 3 defines the boundary they will call across, not the caller itself.

---

## 5. Plugin Architecture

### 5.1 Integration Is One Module, Not Seven

Per `docs/runtime/MODULE_SYSTEM.md § 1` ("nothing about the Runtime hardcodes 'there is a Crawler module'... a module exists because it declares itself against this contract"), **Integration is exactly one new entry** in `docs/runtime/MODULE_SYSTEM.md § 5`'s domain-module table:

| Module | Behavior specified in |
|---|---|
| Integration *(new)* | `docs/integration/` — the module hosts its own nested plugin system (Connectors, per [§5.2](#52-registration-not-modification-one-level-down)), unchanged from the Crawler/Source-Connector shape |

It declares an ordinary `docs/runtime/MODULE_SYSTEM.md § 2` manifest — `module_id`, `capabilities_provided` (one capability per connector operation it currently hosts, resolved dynamically as connectors register — see [§6.3](#63-capability-based-resolution)), `capabilities_required` (`[]` — Integration itself needs nothing from another module beyond the Container and, optionally, the Event Bus), `pipeline_stage_bindings` (`[]` — Integration is not a pipeline stage; a live Connector call is not a Pipeline Definition run), `events_published` (`ConnectorInvoked`, `ConnectorSucceeded`, `ConnectorFailed` — see [§14](#14-security-considerations)), `enabled_by_default: true`.

No individual Connector (`erpnext`, `github`, ...) is its own top-level Runtime module, is discovered by `docs/runtime/PLUGIN_REGISTRY.md`, or appears in `architect plugins list` — exactly as no individual Source Connector does today. The Runtime's Plugin Registry sees **one** entry: "the Integration module."

### 5.2 Registration, Not Modification, One Level Down

Identical discipline to `docs/crawler/CRAWLER_PLUGIN_SYSTEM.md § 2`, restated for connectors: a new Connector becomes active by declaring itself against the fixed Connector Contract ([§6.1](#61-the-connector-contract)) and being discovered through the Integration module's **own** nested, manifest-based registry — enumerated from `integration/connectors/*/` (or an installed-package/registry-file source, per [§12](#12-extension-points)'s marketplace note) at the point `docs/runtime/RUNTIME_BOOT_SEQUENCE.md § 6` reaches the Integration module. Adding connector #8 requires:

1. A new folder under `integration/connectors/`.
2. A manifest declaring the Connector Contract's required fields.
3. Nothing else. **No file under `integration/core/` is edited.** No `if connector == "github"` branch is ever added to `core/` — per `docs/crawler/CRAWLER_PLUGIN_SYSTEM.md § 2`'s identical rule, the moment such a branch would be needed is itself a defect in the boundary.

### 5.3 What a Connector Must Never Do

Verbatim generalization of `docs/crawler/CRAWLER_PLUGIN_SYSTEM.md § 4`, from "source" to "connector":

- Reach into another connector's state, credentials, configuration, or rate-limit budget.
- Bypass the Connector Contract's declared lifecycle (a connector cannot skip `health_check` or invoke an operation before `connect` has succeeded).
- Assert its own trust, confidence, or authority over anything the Knowledge Factory owns — a Connector reading live ERPNext data never gets to claim that data as a validated `Knowledge API`; see [§15, ADR-0007](#15-architectural-decisions-adrs).
- Resolve its own credentials by any path other than the Secrets Resolver ([§8](#8-secrets-architecture)) — no connector reads an environment variable, a file, or a vault directly in its own code.

### 5.4 Isolation Is Structural, Not a Convention

`integration/core/` defines the Connector Contract and the generic lifecycle host; it never imports a concrete connector module. This is the same "Core is closed for modification, plugins are open for extension" shape `docs/crawler/CRAWLER_PLUGIN_SYSTEM.md § 2` already names as this project's Open/Closed Principle application, and the same mechanism `docs/studio/STUDIO_ARCHITECTURE.md § 4` uses to make the Studio's passivity *structural*: a Connector's manifest is validated by the same `docs/runtime/PLUGIN_REGISTRY.md § 4`-style checks (every declared dependency satisfiable, no ambiguous capability, no cycle) applied one level down, inside the Integration module's own nested registry — not a new validation mechanism, the same one, recursed.

---

## 6. Connector Architecture

### 6.1 The Connector Contract

Generalizes `docs/crawler/SOURCE_CONNECTOR_SPEC.md`'s ten required declarations from a **read-only content source** to a **read/write live system**. `SOURCE_CONNECTOR_SPEC.md` itself is unmodified — it remains the Crawler's own, Crawler-scoped contract; this is a sibling specification for a different kind of plugin, reusing what generalizes cleanly and adding what a live, writable system needs that a content source never did.

| # | Declaration | Reused from `SOURCE_CONNECTOR_SPEC.md`? | Notes |
|---|---|---|---|
| 1 | **Identity** — `{ connector_id, display_name, maintained_by, target_system_type, version }` | Yes, reused shape | `target_system_type` is one of `erpnext-site \| mcp-server \| git-hosting-api \| container-runtime \| relational-database \| filesystem \| browser-automation`, or a newly-registered kind the moment one is needed — same open-ended discipline as `source_type`. |
| 2 | **Authentication** — `{ required: bool, method: none \| api_key \| oauth_token \| basic \| mtls \| session_token, credential_reference }` | Yes, reused shape | `credential_reference` per [§8](#8-secrets-architecture) — never a literal secret. A connector declaring `required: true` with no resolvable reference fails to activate loudly, identically to `SOURCE_CONNECTOR_SPEC.md § 1.2`. |
| 3 | **Connection Parameters** | **New** | `{ endpoint_kind: url \| socket \| stdio \| local_path, endpoint_reference }` — `endpoint_reference` follows the same non-literal-secret discipline when it could itself be sensitive (e.g. an internal hostname), resolved the same way as a credential when configuration marks it so. |
| 4 | **Operation Catalog** | **New** | The named operations this connector exposes (e.g. `read_record`, `write_record`, `list_files`, `run_query`, `execute_tool`), each tagged `read \| write` and `idempotent \| non-idempotent` — this is what [§6.5](#65-operation-classification) and [§14](#14-security-considerations)'s destructive-operation gating key off of. A connector with an empty write set is structurally read-only, the same way `docs/studio/STUDIO_ARCHITECTURE.md § 4`'s empty `capabilities_provided` makes the Studio structurally inert. |
| 5 | **Request / Response Shape** | **New** | A reference to the schema each Operation Catalog entry accepts/returns — opaque to the Runtime and to the Container, meaningful only to the connector and its caller, mirroring `docs/runtime/PIPELINE_ENGINE.md § 2`'s "the Engine never inspects `input`/`output` beyond passing them through" applied to connector calls instead of pipeline stages. |
| 6 | **Rate Limits** | Yes, reused shape | `{ requests_per_second, concurrency_limit, respects_platform_headers: bool }` — identical fields to `SOURCE_CONNECTOR_SPEC.md § 1.7`, full design deferred to the same `docs/crawler/RATE_LIMITING.md` mechanism, generalized. |
| 7 | **Retries** | Yes, reused shape | `{ max_attempts, backoff_kind: exponential, base_delay_ms, retryable_status_codes }` — identical to `SOURCE_CONNECTOR_SPEC.md § 1.8`. A **non-idempotent write operation is never automatically retried** by the generic retry mechanism — see [§13](#13-failure-scenarios) — this is the one point where the generalization is *stricter* than the source, precisely because a retried GET is safe and a retried POST may not be. |
| 8 | **Destructive-Operation Gating** | **New** | `{ requires_confirmation: bool, confirmation_scope: per-call \| per-session \| never-required }` — per Operation Catalog entry. A `write` operation classified non-idempotent defaults to `requires_confirmation: true` unless the connector's manifest explicitly, individually overrides it — see [§14](#14-security-considerations). |
| 9 | **Health Check** | **New** (generalizes `docs/runtime/MODULE_SYSTEM.md § 3`'s module-level `health_check()` one layer down) | What "this connector is currently reachable and authenticated" means for this specific target system — a lightweight, read-only, side-effect-free probe operation, always present regardless of what the connector's real Operation Catalog contains. |
| 10 | **Version Awareness** | Not applicable | `SOURCE_CONNECTOR_SPEC.md § 1.10` concerns the *content* a crawl produces being version-scoped; a live Connector call has no equivalent — the live system's own current state *is* the answer, with no version-confidence banding needed. Declared explicitly as "N/A" per this project's "state absence explicitly, never leave a section silently blank" discipline (`SOURCE_CONNECTOR_SPEC.md § 1`'s own stated convention). |

### 6.2 The Connector Request / Response Envelope

Every Connector operation, regardless of `target_system_type`, is invoked through one fixed shape — the direct generalization of `docs/runtime/PIPELINE_ENGINE.md § 2`'s stage contract from *pipeline stages* to *connector calls*:

```
ConnectorRequest:  { operation, parameters (opaque, per Operation Catalog's declared schema),
                      correlation_id, requested_by (which Skill/Agent/Tool issued this) }

ConnectorResponse: { status: success | failure | partial,
                      result (opaque payload),
                      diagnostics (never includes a literal secret — see §8.5),
                      correlation_id }
```

`correlation_id` threads through the same correlation mechanism `docs/runtime/LOGGING_AND_OBSERVABILITY.md § 2` already defines for pipeline runs, so a live connector call and a pipeline run can be correlated in one trace when one triggers the other.

### 6.3 Capability-Based Resolution

The caller (an `MCP` `Tool`'s execution, ultimately) never names a connector directly. It requests a **capability** — e.g. `erpnext.read_record`, `filesystem.write_file` — and `docs/runtime/DEPENDENCY_INJECTION.md § 2`'s existing rule ("resolve by capability, not by type... never to a hardcoded module name") resolves it to whichever enabled connector currently provides it, through the Container, exactly as any other Runtime capability resolves today. This is the literal mechanism satisfying the task's "the planner should never know whether it's talking to ERPNext, MCP, REST, GraphQL, or Filesystem" requirement — it is not a new resolution mechanism, it is the existing one, applied to a new kind of capability.

`docs/runtime/PLUGIN_REGISTRY.md § 4.3`'s ambiguous-capability check applies identically, one level down, inside the Integration module's nested registry: two connectors both claiming `erpnext.write_record` fail validation rather than one being silently picked.

### 6.4 Relationship to `MCP` / `Tool` (Meta-Model Entries 20–21)

`ENGINEERING_META_MODEL.md` entry 20 already states: *"MCP only executes Tools; it holds no architectural judgment of its own."* Entry 21: a `Tool` is *"the smallest unit of 'doing' in the system, as opposed to 'knowing' or 'deciding.'"* Both are **knowledge-layer artifacts** — they document *what* a capability is and *that* it exists, stored under `mcp/servers/MCP-####.md` and `mcp/tools/TL-####.md` per the Repository Folder Mapping's existing `mcp/` reservation ("Execution layer only... nothing in `mcp/` should ever need to reference `rules/` directly").

Sprint 3's Connector is the **Runtime-layer implementation** behind a `Tool` the moment it is actually invoked against a live system. The relationship is exactly `docs/runtime/RUNTIME_ARCHITECTURE.md § 2`'s existing "Two Layers, Not One" split, applied to the execution boundary specifically:

| Layer | Knows about | Owns |
|---|---|---|
| Knowledge (`mcp/`) | *That* a Tool exists, what it conceptually does, which Agents may call it | `MCP`/`Tool` artifact instances |
| Integration (this package) | *How* that capability is mechanically reached — endpoint, auth, wire protocol, retries | Connector implementations |

A `Tool` definition never contains a `credential_reference`, an endpoint, or a retry policy — those belong entirely to the Connector backing it, discovered by capability name at the moment the Tool is actually executed. This is the same non-negotiable split the Meta-Model already draws between "MCP defines capability" and "the Skill/Agent calling the MCP decides whether to use it."

### 6.5 Operation Classification

Every Operation Catalog entry ([§6.1](#61-the-connector-contract), declaration 4) is classified along two independent axes, both declared, never inferred at call time:

| Axis | Values | Consequence |
|---|---|---|
| **Read / Write** | `read`, `write` | A `read` operation is never subject to Destructive-Operation Gating ([§6.1](#61-the-connector-contract), declaration 8); a `write` operation is, by default. |
| **Idempotency** | `idempotent`, `non-idempotent` | An `idempotent` operation may be safely retried by the generic Retries mechanism ([§6.1](#61-the-connector-contract), declaration 7); a `non-idempotent` one is never automatically retried — a failure surfaces to the caller instead, per [§13](#13-failure-scenarios). |

This is a direct generalization of `docs/runtime/STORAGE_ABSTRACTION.md § 2`'s own idempotent-write requirement ("a second write of unchanged content is a no-op") to the connector boundary, where — unlike Storage's own controlled `write` operation — idempotency cannot be assumed and must instead be truthfully declared per operation.

---

## 7. Knowledge Graph Architecture

### 7.1 What Remains Frozen

`docs/knowledge-pipeline/KNOWLEDGE_GRAPH_SPEC.md` is **not modified**. Its node structure (`KG-NNNN: { wraps, wraps_type, edges }`), its nine-member relationship vocabulary (`depends_on`, `implements`, `extends`, `replaces`, `conflicts_with`, `related_to`, `deprecated_by`, `supersedes`, `references`), its node-creation rule ("created automatically the moment its wrapped artifact gains its first relationship edge"), and its append-only edge discipline all stand exactly as written. Sprint 2's `knowledge/artifacts/envelope.py` already implements the envelope-level `relationships`/`dependencies` fields this spec requires — no schema change is needed anywhere in `knowledge/artifacts/`.

### 7.2 What Sprint 3 Adds: the Deferred Mechanics

`KNOWLEDGE_GRAPH_SPEC.md § 5` explicitly deferred: *"node/edge storage and traversal are an implementation concern deferred entirely."* Sprint 3 is that deferral being addressed, architecturally, for the first time. It also completes a piece Sprint 2 itself explicitly deferred: `SPRINT2_IMPLEMENTATION_PLAN.md § 2` scoped `knowledge.graph_build`'s Pipeline Definition to three of its four frozen stages (Extraction, Pattern Extraction, Conflict Resolution), naming **Graph Node/Edge Materialization** as the stage left for "whichever future Sprint builds the Knowledge Graph module." This is that Sprint, and this section is that stage's architecture.

### 7.3 Graph Build Engine

A new Pipeline Definition stage, `graph_materialization`, bound to a capability the new Knowledge Graph module provides — completing `knowledge.graph_build`'s fourth, previously-unregistered stage per `docs/runtime/PIPELINE_ENGINE.md § 4`'s table. Its input is exactly what Sprint 2's `knowledge.validation` pipeline already produces: a `ContentArtifact` with `status: validated`. Its behavior:

1. For each `RelationshipEdge`/`DependencyEdge` already present on the validated artifact's envelope (Sprint 2 fields, unchanged), materialize the corresponding `KG` node (creating it on first edge, per `KNOWLEDGE_GRAPH_SPEC.md § 4`) and the corresponding graph edge.
2. No new relationship is invented here — the Graph Build Engine is a **projection** step, turning envelope-embedded edges into a traversable structure; the set of relationships an artifact participates in is decided entirely upstream, by Extraction/Pattern Extraction/Conflict Resolution ([§7 of `SPRINT2_REVIEW_PACKAGE.md`](SPRINT2_REVIEW_PACKAGE.md), unchanged).
3. Per `KNOWLEDGE_GRAPH_SPEC.md § 3`'s directionality discipline, a symmetric relationship (`conflicts_with`, `related_to`) is materialized once, as a single undirected edge — the Graph Build Engine is the enforcement point for this rule, not merely a documented expectation.

### 7.4 Graph Store Adapter

Mirrors `docs/runtime/STORAGE_ABSTRACTION.md`'s pattern exactly — a backend-agnostic adapter contract, no product chosen:

| Storage Abstraction (existing) | Graph Store Adapter (new, same shape) |
|---|---|
| Addressing: `namespace + key` | Addressing: `node_id`, or `(source_node_id, relationship, target_node_id)` for an edge |
| Operations: `read`, `write`, `exists`, `list`, `delete`, `content_hash` | Operations: `create_node`, `create_edge`, `get_node`, `edges_of(node_id, relationship_filter)`, `traverse(seed_ids, relationship_filter, max_depth, direction)` |
| `delete` reserved, never called on permanent zones | No delete operation at all — `KNOWLEDGE_GRAPH_SPEC.md § 4`'s "edges are appended, never overwritten... gains a `retracted` flag" already forbids deletion; the Adapter contract has no operation that could violate it |
| Adapter selection: `CONFIGURATION_SYSTEM.md § 2` Global/Environment layer | Identical: Graph Store Adapter selection is a Configuration System setting, resolved once at boot, injected via the Container |
| Testability: in-memory Adapter satisfies the same contract | Identical: an in-memory Graph Store Adapter is a valid substitute for any real backend in tests, no different code path |

**No backend is chosen.** Candidate backend *kinds* (a property graph database, a relational schema with adjacency tables, an in-memory structure for small deployments) remain an implementation decision explicitly deferred past this package, per `KNOWLEDGE_GRAPH_SPEC.md § 5`'s own scope boundary, now inherited by this Adapter contract rather than left unaddressed.

### 7.5 Traversal Interface

One operation, `traverse(seed_ids, relationship_filter, max_depth, direction)`, is the **only** sanctioned way any caller (a future Retrieval module, an Agent, a Studio view) reads the graph. It returns an ordered walk outward from `seed_ids`, never a full-graph scan — the exact constraint `KNOWLEDGE_GRAPH_SPEC.md § 5` already imposes ("every traversal... must be expressible as a bounded-depth walk from a small seed set... never a full-graph scan"), now given a concrete interface shape to be bounded *by*. `max_depth` is mandatory, with no "unbounded" value accepted — a caller wanting a large walk states a large, still-finite number, never an absence of one.

### 7.6 Worked Example — Grounded in Already-Shipped Sprint 2 Code

The task's own example (*Sales Invoice depends_on Customer; Customer depends_on Address*) maps directly onto artifact types Sprint 2 already implements, with no new concept required:

- `Sales Invoice`, `Customer`, and `Address` DocType schemas are each extracted as a `KnowledgeAPI` artifact (`content.interface_kind = "doctype-field"`), by Sprint 2's already-shipped `knowledge/extraction/rules.py::extract_from_official_source_code`, reading a `doctype_schemas` entry.
- A Link field from `Sales Invoice` to `Customer` (and `Customer` to `Address`) is exactly the kind of fact that becomes a `DependencyEdge(target_id=<Customer's KA id>, reason="Sales Invoice.customer is a Link field to Customer")` on the `Sales Invoice` `KnowledgeAPI` artifact's envelope — using the `dependencies`/`relationships` fields `knowledge/artifacts/envelope.py` already defines, unchanged.
- Once both artifacts are `validated`, the Graph Build Engine ([§7.3](#73-graph-build-engine)) materializes one `depends_on` edge between their `KG` nodes.
- A future Agent asking "what does creating a Sales Invoice actually require?" issues `traverse(seed_ids=[<Sales Invoice KA id>], relationship_filter=[depends_on], max_depth=2)` and receives the ordered chain `Sales Invoice → Customer → Address` — the same reasoning-chain shape `docs/knowledge-pipeline/RETRIEVAL_STRATEGY.md § 5` already specifies for the rules-only case, now genuinely multi-hop and cross-artifact.

No extraction rule change is required to produce this — `doctype_schemas`-sourced `KnowledgeAPI` artifacts populating `dependencies` from a DocType's own Link fields is a natural extension of the rule Sprint 2 already ships, left as a small, explicitly-named piece of [§17](#17-future-work) rather than assumed to already exist.

---

## 8. Secrets Architecture

### 8.1 The Constraint Already Frozen

`docs/runtime/CONFIGURATION_SYSTEM.md § 6` already states, as a hard validation rule: *"no literal credential value is ever stored in configuration, at any layer — only a `credential_reference` pointing to where one is resolved... a configuration value that looks like a credential... fails validation outright."* Sprint 3 does not change this rule. It defines, for the first time, what a `credential_reference` actually resolves **through**.

### 8.2 `credential_reference` Schemes

A `credential_reference` is a scheme-prefixed string identifying both *where* to resolve a secret and *which* Secrets Resolver backend understands that scheme:

| Scheme | Resolves from | Typical use |
|---|---|---|
| `env://VAR_NAME` | The process's own OS environment variables | CI, containerized deployments where secrets are already injected by the orchestrator |
| `dotenv://VAR_NAME` | A local `.env` file (never committed — see [§8.4](#84-storage-conventions-never-repository-content)) | Local development |
| `profile://<profile_name>/<key>` | A named Profile's own scoped secrets file | Multi-customer/multi-environment operation — see [§8.3](#83-profiles) |
| `vault://<path>` | A future HashiCorp-Vault-or-equivalent integration | Production, multi-operator deployments — **not implemented in Sprint 3**, reserved scheme only |

Every Secrets Resolver backend satisfies one fixed contract — `resolve(credential_reference) -> secret_value | resolution_failure` — the same "one contract, many backends, chosen by configuration" shape as the Storage Adapter ([§7.4](#74-graph-store-adapter)) and the Graph Store Adapter, applied a third time.

### 8.3 Profiles

A **Profile** (`Development`, `Production`, `Customer A`, `Customer B`, `Local ERP`, `Cloud ERP`, and any future name) is **not a new, seventh configuration layer**. It is a named instance of `docs/runtime/CONFIGURATION_SYSTEM.md § 2`'s existing **Environment** layer, whose own text already reads *"`dev` / `staging` / `production`-style overrides"* — illustrative examples, not a closed enum. Sprint 3's only addition is: an Environment-layer name may pair with a Profile-scoped secrets file, resolved via `profile://`, so that switching which live ERPNext instance (or which customer's credentials) is in play is a single configuration selection, never a code change and never a shared secrets file edited in place.

Each Profile's own credentials live in a Profile-scoped, git-ignored file — never inside `docs/`, never inside this package, never inside any architecture artifact, per [§8.4](#84-storage-conventions-never-repository-content).

### 8.4 Storage Conventions: Never Repository Content

- No `.env` file, no Profile secrets file, and no Vault path is ever committed. `.gitignore` covers the conventional locations (`.env`, `.secrets/`, `profiles/*.secrets`) the moment Sprint 3 is implemented — a repository-hygiene requirement carried into [§18](#18-migration-strategy), not deferred.
- This package itself, and every document it proposes splitting into ([§3.2](#32-documentation-family-proposed-post-approval-split)), contains **zero** literal credential values, real or fabricated-but-realistic-looking — every example in this package shows a `credential_reference` (a pointer), never a resolved value. This extends `CONFIGURATION_SYSTEM.md § 6`'s existing rule (which governs *runtime configuration*) to *architecture artifacts* as well — a small, explicit widening, named here rather than left implicit. See [§15, ADR-0005](#15-architectural-decisions-adrs).

### 8.5 Resolution Timing and Non-Persistence

A `credential_reference` is resolved **just-in-time**, at the moment a Connector actually needs the secret to authenticate a call — never resolved-and-cached inside the Configuration System, never written back into any configuration layer, and never present in a `ConnectorResponse`'s `diagnostics` field ([§6.2](#62-the-connector-request--response-envelope)). This mirrors `docs/runtime/LOGGING_AND_OBSERVABILITY.md § 1`'s existing "never log a literal secret" rule, applied one step earlier — at the point of resolution, not merely at the point of logging.

### 8.6 Multiple Profiles, One Mechanism

`Development`, `Production`, `Customer A`, `Customer B`, `Local ERP`, `Cloud ERP` are not six different mechanisms — they are six different **values** of the same Environment-layer key, each optionally paired with its own `profile://`-addressed secrets file. Switching profiles is a single Configuration System selection (`docs/runtime/RUNTIME_BOOT_SEQUENCE.md § 4`'s existing Configuration Loading step, unchanged), resolved before any Connector activates — a Connector requiring `required: true` authentication whose active Profile has no matching `profile://` entry fails to activate loudly, per [§6.1](#61-the-connector-contract) declaration 2, identically to `SOURCE_CONNECTOR_SPEC.md § 1.2`'s existing behavior for Source Connectors.

---

## 9. Configuration Architecture

### 9.1 The Six Layers Are Unmodified

`docs/runtime/CONFIGURATION_SYSTEM.md § 2`'s six layers (Runtime defaults → Global → Environment → Module → Pipeline → Connector) are reused exactly as specified. Two observations, both additive, neither a change to the layer model itself:

1. **The "Connector" layer already generalizes.** `CONFIGURATION_SYSTEM.md § 2`'s sixth layer was named and scoped for `docs/crawler/SOURCE_CONNECTOR_SPEC.md`'s Source Connectors specifically, but nothing in its definition is Crawler-specific — "a single Source Connector's own ten declarations, already fully specified by that document and simply hosted at this layer, not redefined by it" reads, unchanged, as "a single Connector's own declarations ([§6.1](#61-the-connector-contract)), hosted at this layer." Integration Connectors use the identical sixth layer. No seventh layer is introduced.
2. **Profiles are Environment-layer values**, per [§8.3](#83-profiles) — not a new layer, not a new mechanism.

### 9.2 Integration Module Configuration

The Integration module's own settings (which connectors are enabled, per-connector rate-limit overrides, the active Profile) resolve through the existing Module layer (`docs/runtime/CONFIGURATION_SYSTEM.md § 2`, layer 4), populated from the Integration module's own `config_schema_ref` — no new configuration-loading mechanism, the same one every Sprint 1/2 module already uses.

### 9.3 `ConfigurationChanged` Reuse

`CONFIGURATION_SYSTEM.md § 5` already publishes a `ConfigurationChanged` event to the Event Bus whenever a configuration *value* changes, at any layer. A Connector being enabled/disabled, or a Profile switch, is exactly such a value change — it is already covered by this existing event, requiring no new event type.

---

## 10. Data Flow

### 10.1 A Live Action, End to End

```
Skill/Agent (Planning)                 [decides WHAT — unbuilt this Sprint, named for context]
      │  invokes a named Tool (mcp/tools/TL-####.md)
      ▼
MCP execution boundary                  [ENGINEERING_META_MODEL.md entry 20 — holds no judgment]
      │  requests a capability, e.g. "erpnext.write_record"
      ▼
Container  (docs/runtime/DEPENDENCY_INJECTION.md, unmodified)
      │  resolves capability → the one enabled Connector providing it
      ▼
Integration module → Connector (e.g. erpnext)
      │  needs credentials to authenticate the call
      ▼
Secrets Resolver  (§8)
      │  resolves credential_reference → secret value, just-in-time, never cached
      ▼
Connector executes against the live external system
      │  ConnectorRequest → external system → ConnectorResponse (§6.2)
      ▼
Result flows back up through Container → MCP → Skill/Agent
      │  ConnectorInvoked / ConnectorSucceeded / ConnectorFailed published to Event Bus
      ▼
(never automatically) Knowledge Factory  — a live result does NOT become a Knowledge
      Artifact without an explicit, separately-scoped re-ingestion path (§15, ADR-0007)
```

### 10.2 Knowledge Graph Population

```
Extractor → Pattern Extraction → Conflict Resolution → Validator (8 gates)   [Sprint 2, unmodified]
      │  produces a ContentArtifact with status: validated
      ▼
Graph Build Engine  (§7.3, new)
      │  reads the artifact's existing relationships/dependencies fields
      ▼
Graph Store Adapter  (§7.4, new — interface only, no backend chosen)
      │  create_node / create_edge
      ▼
Traversal Interface  (§7.5)
      │  available to: a future Retrieval module, an Agent reasoning about a proposal,
      │  a future Studio graph view — never to a live Connector call
```

---

## 11. Sequence Diagrams

### 11.1 Boot — Integration Module's Nested Connector Registration

Extends `docs/runtime/RUNTIME_BOOT_SEQUENCE.md § 6` ("Connector Registration"), which today names only the Crawler module:

```
Runtime Boot                Plugin Registry           Integration Module        Connector Registry (nested)
    │  Step 2: Discovery          │                            │                            │
    │─────────────────────────────►  finds "Integration"       │                            │
    │                              │  manifest, registers it   │                            │
    │  Step 3: Dependency Val.     │  (as one opaque module)   │                            │
    │  Step 4: Configuration       │                            │                            │
    │  Step 5: Pipeline Reg.       │                            │                            │
    │  Step 6: Connector Reg.  ────┼───────────────────────────►  init() runs                │
    │  (now also covers            │                            │─────────────────────────► │
    │   Integration, not only      │                            │  enumerate integration/    │
    │   Crawler — §15 ADR-0003)    │                            │  connectors/*/, validate    │
    │                              │                            │  each against §6.1           │
    │                              │                            │◄───────────────────────────│
    │                              │                            │  nested registry built       │
    │  Step 7: Health Checks   ────┼───────────────────────────►  health_check() per            │
    │                              │                            │  connector (§6.1 decl. 9)     │
    │  Step 8: Ready                │                            │                            │
```

Exactly as `RUNTIME_BOOT_SEQUENCE.md § 6` already states for the Crawler case: this nested pass is *"invisible to the Runtime's own Plugin Registry, which only ever sees one entry."*

### 11.2 A Tool Invocation Reaching a Live Connector

```
Agent/Skill      MCP/Tool         Container        Integration/Connector    Secrets Resolver   External System
    │  invoke Tool   │                 │                    │                     │                   │
    │───────────────►│  resolve         │                    │                     │                   │
    │                │  capability      │                    │                     │                   │
    │                │─────────────────►│  find provider     │                     │                   │
    │                │                 │───────────────────►│                     │                   │
    │                │                 │                    │  resolve credential │                   │
    │                │                 │                    │────────────────────►│                   │
    │                │                 │                    │◄────────────────────│  secret (transient) │
    │                │                 │                    │  ConnectorRequest    │                   │
    │                │                 │                    │──────────────────────────────────────────►│
    │                │                 │                    │◄──────────────────────────────────────────│
    │                │                 │                    │  ConnectorResponse   │                   │
    │                │                 │◄───────────────────│                     │                   │
    │                │◄────────────────│                    │                     │                   │
    │◄───────────────│  result          │                    │                     │                   │
    │                │  [Event Bus: ConnectorInvoked / ConnectorSucceeded published throughout]         │
```

### 11.3 Destructive Write Requiring Confirmation

```
Agent/Skill         MCP/Tool         Integration/Connector
    │  invoke write   │                    │
    │  operation       │                    │
    │─────────────────►│  Operation Catalog  │
    │                  │  entry marked       │
    │                  │  requires_confirmation: true (§6.1 decl. 8)
    │                  │────────────────────►│
    │                  │◄────────────────────│  ConnectorResponse:
    │                  │                    │  status = failure,
    │◄─────────────────│                    │  diagnostics = "confirmation required, not yet granted"
    │  [caller must re-invoke with confirmation explicitly attached at the requested_by / correlation
    │   layer of ConnectorRequest — this package defines that this gate exists and blocks by default;
    │   the confirmation-granting UX itself is unbuilt, out of scope per §17]
```

### 11.4 Knowledge Graph Traversal (Read-Only, No Live Call)

```
Agent          Traversal Interface        Graph Store Adapter
    │  traverse(     │                            │
    │   seed, filter, │                            │
    │   max_depth)     │                            │
    │────────────────►│  bounded-depth walk          │
    │                  │─────────────────────────────►│
    │                  │◄─────────────────────────────│  ordered node/edge chain
    │◄─────────────────│                            │
    │  [no Connector, no Secrets Resolver, no external system is ever touched by this path]
```

---

## 12. Extension Points

| Extension | Mechanism | Cost of adding it |
|---|---|---|
| Connector #8 (and beyond) | New folder under `integration/connectors/`, one manifest, [§5.2](#52-registration-not-modification-one-level-down) | Same as adding Source Connector #50 today — one Discovery-equivalent implementation (here: the connector's own auth + operation handling) and a manifest; zero shared-code edits |
| New Secrets Resolver backend (e.g. Vault) | Implement the fixed `resolve(credential_reference)` contract, register its scheme prefix | Zero change to any Connector — a Connector only ever sees "credential resolved" or "resolution failed," never which backend served it |
| New Graph Store Adapter backend | Implement [§7.4](#74-graph-store-adapter)'s fixed operation set, select via Configuration | Zero change to the Graph Build Engine or the Traversal Interface, per `STORAGE_ABSTRACTION.md § 4`'s identical existing guarantee for content-addressed storage |
| Marketplace plugin discovery | A fourth discovery source alongside directory-scan/installed-package/registry-file, per `docs/runtime/PLUGIN_REGISTRY.md § 1`'s own already-open list of discovery mechanisms | No change to validation, capability discovery, or the Connector Contract — only *where* a manifest is found changes |
| Distributed / remote Connector execution | `docs/runtime/RUNTIME_ARCHITECTURE.md § 7`'s existing "without redesign" non-functional requirement — a Connector call is already capability-resolved through the Container, the same seam a future distributed worker pool already relies on for Pipeline stages | No architectural change; only *where* a Connector's process physically runs changes |
| Live-Connector-data re-ingestion into Knowledge | An explicit, separately-scoped future pipeline connecting Connector output back into `knowledge.graph_build`'s Extraction stage, with its own trust/validation treatment | Deliberately **not** free or automatic — see [§15, ADR-0007](#15-architectural-decisions-adrs) and [§17](#17-future-work) |

---

## 13. Failure Scenarios

| Scenario | Detected at | Behavior |
|---|---|---|
| Connector declares `required: true` auth with no resolvable `credential_reference` | Connector activation (nested registration, [§11.1](#111-boot--integration-modules-nested-connector-registration)) | Boot-blocking for that connector only (mirrors `SOURCE_CONNECTOR_SPEC.md § 1.2`'s "fails to activate, loudly, never silently falls back") — other connectors and the rest of the Runtime are unaffected, per `docs/runtime/RUNTIME_BOOT_SEQUENCE.md § 7`'s existing per-module-optional health-check gating |
| Two connectors both declare the same capability | Nested dependency validation ([§6.3](#63-capability-based-resolution)) | Boot-blocking, per `PLUGIN_REGISTRY.md § 4.3`'s ambiguous-capability rule, applied one level down |
| A live external system is unreachable at call time | Connector invocation | Classified `read`+`idempotent` → retried per the connector's declared Retry policy ([§6.1](#61-the-connector-contract) decl. 7); `write`+`non-idempotent` → **never** auto-retried, surfaced to the caller as `ConnectorResponse.status = failure` immediately, so a caller can decide whether re-invoking is safe (only the caller knows if the first attempt's side effect actually landed) |
| A destructive write is attempted without confirmation | Before the call reaches the external system ([§11.3](#113-destructive-write-requiring-confirmation)) | Rejected at the Connector boundary, `status = failure`, `diagnostics` states confirmation is required — the external system is never touched |
| Secrets Resolver backend itself is unavailable (e.g. Vault down) | Credential resolution, prior to any external call | The requesting Connector's `health_check` reports unhealthy — never silently degrades to an unauthenticated call, per `SOURCE_CONNECTOR_SPEC.md § 1.2`'s existing "never silently falls back to unauthenticated access" discipline, generalized |
| Wrong Profile active for the intended target (Customer A's connector reachable while Customer B's Profile is loaded) | Configuration Loading ([§9.2](#92-integration-module-configuration)), before any connector activates | Fails closed — a Connector requiring a `profile://` reference not present in the currently-active Profile is treated identically to a missing credential (first row of this table), never falls through to a different Profile's file |
| Graph traversal requests unbounded depth | Traversal Interface ([§7.5](#75-traversal-interface)) | Rejected — `max_depth` is a mandatory, finite parameter; there is no "traverse everything" call in the contract |
| A Connector attempts to bypass its own declared lifecycle (invoke before `connect`, skip `health_check`) | Connector Contract enforcement, [§5.3](#53-what-a-connector-must-never-do) | Treated as a contract violation, the same category of defect `CRAWLER_PLUGIN_SYSTEM.md § 4` already names for a Source Connector reaching into shared state — not a runtime error to catch and continue past, a boundary the architecture states must not exist in a compliant connector |

---

## 14. Security Considerations

1. **Least-privilege capability grants.** A connector's manifest declares its full Operation Catalog ([§6.1](#61-the-connector-contract) decl. 4) up front; nothing about the Container's capability-resolution model ([§6.3](#63-capability-based-resolution)) allows a caller to invoke an operation a connector didn't declare. An Agent/Skill can only ever reach capabilities actually registered — there is no generic "run arbitrary operation on connector X" escape hatch anywhere in this architecture.
2. **Credential isolation per Profile.** Each Profile's secrets are scoped to their own `profile://` file ([§8.3](#83-profiles)); nothing in the Secrets Resolver contract allows cross-profile resolution — a Connector activated under "Customer A" can only ever resolve `profile://Customer A/...` references, never "Customer B"'s, by construction of which Profile is active at Configuration Loading time ([§13](#13-failure-scenarios)'s "wrong Profile" row).
3. **Destructive-operation gating is default-on, not opt-in.** [§6.1](#61-the-connector-contract) decl. 8 defaults `requires_confirmation: true` for any `write`+`non-idempotent` operation — a connector author must explicitly, individually declare an override; the safe behavior is the one requiring no extra decision.
4. **No secret ever persists outside the Secrets layer.** Not in Configuration ([§9.1](#91-the-six-layers-are-unmodified), inherited unmodified from `CONFIGURATION_SYSTEM.md § 6`), not in a log (`LOGGING_AND_OBSERVABILITY.md § 1`, inherited), not in a `ConnectorResponse.diagnostics` field ([§8.5](#85-resolution-timing-and-non-persistence)), and not in any architecture artifact including this one ([§8.4](#84-storage-conventions-never-repository-content)).
5. **Planning never bypasses Execution.** An Agent/Skill (Planning) reaches a Connector (Execution) **only** through an `MCP` `Tool` — there is no path in this architecture from the Planning layer directly to `integration/connectors/`. This is the same non-negotiable split `ENGINEERING_META_MODEL.md` entry 20 already states for MCP generally, restated as a hard boundary specifically at the live-system execution point, where the cost of it being violated is highest.
6. **The Knowledge Graph is read-only with respect to live systems.** Traversal ([§7.5](#75-traversal-interface)) never triggers a Connector call, and a Connector's output never silently becomes a graph node — see [§15, ADR-0007](#15-architectural-decisions-adrs). This prevents a live customer's private operational data from being indistinguishable, at query time, from validated, versioned framework knowledge.
7. **Every connector invocation is an auditable event.** `ConnectorInvoked`/`ConnectorSucceeded`/`ConnectorFailed` ([§5.1](#51-integration-is-one-module-not-seven)) publish to the Event Bus for every call, unconditionally — this project's standing Traceability principle (`ENGINEERING_META_MODEL.md § Design Principles`), applied to live actions for the first time.
8. **Multi-tenant boundary is a Profile boundary, not a code boundary.** This is named explicitly as a risk, not only a guarantee — see [§16](#16-risks), item on Profile discipline.

---

## 15. Architectural Decisions (ADRs)

Per `adr/README.md`'s existing format ("the context, the alternatives considered, what was decided, and the consequence accepted"), continuing the numbering `ADR-0001`/`ADR-0002` already established.

### ADR-0003 — Integration Is a Nested Plugin System Inside One Module, Not Seven Top-Level Modules

**Context:** The task names seven initial connector kinds (ERPNext, MCP, GitHub, Docker, PostgreSQL, Filesystem, Playwright) and asks for a Plugin System supporting them, plus future ones.
**Alternatives considered:** (a) each connector kind is its own top-level Runtime module, discovered directly by `docs/runtime/PLUGIN_REGISTRY.md`; (b) one Integration module hosting all connectors as a nested plugin system, mirroring Crawler/Source-Connectors.
**Decision:** (b). `docs/runtime/MODULE_SYSTEM.md § 1` already states the Runtime "never special-cases any module by name," and seven-plus near-identical top-level modules (each needing its own manifest, its own dependency-graph entry, its own boot-sequence participation) would multiply Runtime-level bookkeeping for entities that share one contract. The Crawler/Source-Connector precedent already proves the nested shape scales ("today's 48 cataloged sources require on the order of the eight source types already enumerated, not 48 separate connectors," `CRAWLER_PLUGIN_SYSTEM.md § 6`).
**Consequence:** `docs/runtime/RUNTIME_BOOT_SEQUENCE.md § 6` ("Connector Registration"), which today reads "specifically for the Crawler module," must be read as generalizing to any module hosting a nested plugin system — Integration included. This is a **documentation widening, not a redesign**: the mechanism described was already generic ("the same fractal shape at the layer above," `RUNTIME_BOOT_SEQUENCE.md § 6`'s own words); only its example was singular. Formal approval of this ADR is the trigger to update that one sentence in `RUNTIME_BOOT_SEQUENCE.md` to name both modules explicitly.

### ADR-0004 — The Connector Contract Is a New, Sibling Specification, Not a Modification of `SOURCE_CONNECTOR_SPEC.md`

**Context:** `docs/crawler/SOURCE_CONNECTOR_SPEC.md`'s ten declarations are frozen and Crawler-scoped (read-only content sources). Sprint 3's connectors need read **and** write, against live systems, not archived content.
**Alternatives considered:** (a) extend `SOURCE_CONNECTOR_SPEC.md` in place with new optional fields for write support; (b) a new, sibling Connector Contract ([§6.1](#61-the-connector-contract)), reusing what generalizes and adding what doesn't.
**Decision:** (b). `SOURCE_CONNECTOR_SPEC.md`'s own authority line scopes it to "the one fixed contract every Source Connector implements" — retrofitting write semantics, destructive-operation gating, and live health checks onto a document whose entire design center is "read-only, archival, version-scoped content" would be exactly the kind of contested redesign this project's standing discipline forbids.
**Consequence:** Two contracts now exist, deliberately: `SOURCE_CONNECTOR_SPEC.md` (unchanged, Crawler-only) and this package's Connector Contract (Integration-only). Any future third contract (should one arise) faces the same choice, decided the same way: reuse the shape that generalizes, never force-fit.

### ADR-0005 — `credential_reference` Resolution Is a New Runtime Capability (Secrets Resolver), and Architecture Artifacts Are Bound by the Same No-Literal-Secret Rule as Configuration

**Context:** `CONFIGURATION_SYSTEM.md § 6` already forbids literal secrets in configuration but never specified what a `credential_reference` resolves through.
**Alternatives considered:** (a) leave resolution as an implementation detail each module handles ad hoc; (b) one Runtime-level Secrets Resolver capability, contract-based, multi-backend, mirroring the Storage Adapter.
**Decision:** (b), for the same reason Storage Adapter exists at all: ad hoc, per-module secret handling is exactly the "scattered ad hoc reads" `CONFIGURATION_SYSTEM.md § 1` already rejected for configuration generally.
**Consequence:** A previously-silent gap (what does `credential_reference` actually mean, mechanically) is closed. Additionally decided, narrowly: this project's documents — including this one — never contain literal-looking secret values, extending `CONFIGURATION_SYSTEM.md § 6`'s rule from "runtime configuration" to "any artifact this repository produces," since an architecture document is exactly the kind of place a well-meaning illustrative example could otherwise leak a realistic-looking credential.

### ADR-0006 — Knowledge Graph Storage/Traversal Is a New Runtime Module, Populated From Sprint 2's Existing Envelope Fields — No New Artifact Schema

**Context:** `KNOWLEDGE_GRAPH_SPEC.md` already defines nodes/edges/relationships but explicitly deferred storage and traversal. Sprint 2 already ships `relationships`/`dependencies` fields on every `ContentArtifact`.
**Alternatives considered:** (a) a new artifact type or envelope field to carry graph-specific data; (b) a Graph Build Engine that projects Sprint 2's already-existing fields into a separately-stored graph structure, with no schema change.
**Decision:** (b). Every fact the graph needs (which artifact relates to which, how) already exists on the envelope Sprint 2 shipped; inventing a parallel representation would violate this project's "single source of truth" discipline (the same discipline that makes `RULE_INDEX.yaml` "compiled... never hand-edited" rather than a second authority).
**Consequence:** The Knowledge Graph module has a read/derive relationship to `knowledge/artifacts/`, never a write relationship to it — an artifact's `relationships` field remains authored entirely by Extraction/Pattern Extraction/Conflict Resolution (Sprint 2, unchanged); the Graph Build Engine only ever reads it.

### ADR-0007 — Live Connector Output Never Automatically Becomes a Knowledge Artifact

**Context:** A Connector reading live ERPNext data (e.g., a specific customer's actual DocType customizations) produces information that superficially resembles what Extraction produces from official sources.
**Alternatives considered:** (a) let Connector reads feed directly into the Extraction pipeline, treating a live read as just another source type; (b) keep the two paths structurally separate, with no automatic promotion.
**Decision:** (b). Extraction's entire trust model — Trust Score thresholds, Source Verification, the eight validation gates — is built around **official, generally-applicable** sources (`docs/knowledge-pipeline/KNOWLEDGE_SOURCE_CATALOG.md`, `KNOWLEDGE_VALIDATION_SPEC.md`). A live customer's private, one-off configuration is neither official nor generally applicable, and silently blending it into the same trusted graph every customer's Agent draws on would let one customer's private, possibly-idiosyncratic setup masquerade as validated framework knowledge for another.
**Consequence:** A live Connector read stays operational/transient — visible to the Agent that requested it, published as an auditable event, but never a `KG` node unless a human-gated, separately-scoped future re-ingestion pipeline (named, not built, in [§17](#17-future-work)) explicitly promotes it, subject to the *same* eight validation gates everything else goes through, no shortcut.

### ADR-0008 — Profiles Are Environment-Layer Values, Not a New Configuration Layer

**Context:** The task asks for named profiles (Development, Production, Customer A, Customer B, Local ERP, Cloud ERP) as a first-class concept.
**Alternatives considered:** (a) a new, seventh Configuration System layer, "Profile," sitting between Environment and Module; (b) Profiles are simply named values of the existing Environment layer.
**Decision:** (b). `CONFIGURATION_SYSTEM.md § 2`'s own text already treats its Environment examples (`dev`/`staging`/`production`) as illustrative, not exhaustive; adding a seventh layer for what is structurally identical behavior (a named override tier) would duplicate a mechanism that already generalizes, contradicting this project's own "don't force a contested choice when an existing shape already fits" discipline.
**Consequence:** No change to `CONFIGURATION_SYSTEM.md § 2`'s six-layer precedence order. "Which Profile is active" is answered by the same mechanism that already answers "which Environment is active" today.

---

## 16. Risks

| Risk | Nature | Mitigation stated in this package |
|---|---|---|
| Secrets Resolver backend selection is deferred | Real, not hypothetical — `.env`/`dotenv://` and `env://` are simple enough to be low-risk defaults, but `vault://` is named, not designed | [§17](#17-future-work) names concrete backend selection as follow-on work, gated by its own review |
| Graph Store Adapter backend selection is deferred | Same nature | Same treatment; [§7.4](#74-graph-store-adapter)'s interface is deliberately backend-agnostic so this deferral costs nothing structurally |
| No Agent/Planner runtime exists yet | This package defines the boundary an Agent will call across, not the Agent itself | Explicitly named, not hidden — [§2](#2-architecture-overview) and every "Planning" reference in this package is marked "unbuilt this Sprint, named for context" |
| Multi-tenant Profile isolation depends on disciplined operational use, not only architecture | An operator activating the wrong Profile is a human/process failure the architecture can detect ([§13](#13-failure-scenarios)'s "wrong Profile" row fails closed) but cannot prevent someone from attempting | Fail-closed behavior is the architectural mitigation; process-level discipline (which Profile an operator selects) is out of this package's scope |
| Connector proliferation without governance | Adding connector #50 is architecturally cheap ([§12](#12-extension-points)); cheap addition can mean uncurated addition | Mirrors the exact risk `CRAWLER_PLUGIN_SYSTEM.md § 6` already accepted for Source Connectors at scale — no new mitigation invented, same tradeoff knowingly re-accepted |
| Destructive-operation gating's confirmation UX is undesigned | [§11.3](#113-destructive-write-requiring-confirmation) defines that the gate exists and blocks by default, not how a human actually grants confirmation | Named explicitly as out of scope in [§17](#17-future-work), not silently assumed solved |
| Live re-ingestion pathway (ADR-0007) is named but not designed | A real customer need ("promote this live fact to shared knowledge") has no architecture yet | Deliberately deferred rather than rushed — see [§17](#17-future-work) |

---

## 17. Future Work

Explicitly out of this package's scope, named so it is not silently assumed solved:

- Concrete Secrets Resolver backend implementation, starting with `env://`/`dotenv://` (lowest risk, no external dependency), then `profile://`, then `vault://`.
- Concrete Graph Store Adapter backend selection and implementation.
- The Agent/Planner runtime itself (`ENGINEERING_META_MODEL.md` entries 14–15, `docs/runtime/RUNTIME_ARCHITECTURE.md § 4.7`'s Agents module) — this package defines the boundary it will call across ([§6.4](#64-relationship-to-mcp--tool-meta-model-entries-2021)), not the runtime that decides what to call.
- The Destructive-Operation confirmation UX ([§11.3](#113-destructive-write-requiring-confirmation)) — who grants confirmation, and how, is unspecified.
- The first real Connector implementations, in the rollout order [§18](#18-migration-strategy) proposes.
- The live-Connector-to-Knowledge re-ingestion pathway named in [§15, ADR-0007](#15-architectural-decisions-adrs) — a genuinely new, human-gated pipeline, not a small addition.
- A future Connector Marketplace ([§12](#12-extension-points)), building on the discovery mechanism already generalized to support it.
- Extending `knowledge/extraction/rules.py`'s `doctype_schemas` handling to populate `dependencies` from DocType Link fields automatically, per [§7.6](#76-worked-example--grounded-in-already-shipped-sprint-2-code)'s worked example — a small, concrete Sprint 2-adjacent follow-on.

---

## 18. Migration Strategy

**No existing Sprint 1 or Sprint 2 file is modified by this architecture.** Integration and Knowledge Graph are net-new module families; every reused pattern ([§1](#1-executive-summary)'s table) is consumed by reference, not by editing the document or code that defines it. The only two existing documents this package proposes a textual widening of, both narrow and both requiring separate, explicit approval before being applied:

1. `docs/runtime/RUNTIME_BOOT_SEQUENCE.md § 6` — generalize "specifically for the Crawler module" to name Integration as well (per [§15, ADR-0003](#15-architectural-decisions-adrs)).
2. `ENGINEERING_META_MODEL.md`'s Repository Folder Mapping — add `integration/` and `docs/integration/` as reserved-not-yet-created entries, using the exact courtesy wording already used for `runtime/`, `crawler/`, and `studio/`.

**Proposed implementation order**, once this package is approved (mirroring how Sprint 2 sequenced its own internal build order — schemas first, then the pieces that depend on them):

1. **Secrets Resolver** ([§8](#8-secrets-architecture)) — `env://`/`dotenv://` only. Nothing else in this package can be exercised end-to-end without it, and it has no dependency on anything else here.
2. **Configuration System's Profile convention** ([§9](#9-configuration-architecture)) — no code change to the six-layer model itself, only the operational convention of naming Environment values as Profiles.
3. **Integration module skeleton + Connector Contract** ([§5](#5-plugin-architecture), [§6.1](#61-the-connector-contract)) — the host and the contract, with zero connectors registered yet (structurally valid, per `docs/studio/STUDIO_ARCHITECTURE.md § 4`'s precedent for a module that legitimately provides nothing at first).
4. **First real Connector: Filesystem** — chosen deliberately first because it needs no live secret and no network dependency, the lowest-risk way to prove the Connector Contract and capability-resolution path ([§6.3](#63-capability-based-resolution)) end to end.
5. **Graph Build Engine + in-memory Graph Store Adapter** ([§7.3](#73-graph-build-engine), [§7.4](#74-graph-store-adapter)) — independent of the Connector work above; can proceed in parallel once Sprint 2's artifact fields are the only dependency, which they already satisfy today.
6. **Remaining Connectors** (ERPNext, GitHub, PostgreSQL, Docker, MCP, Playwright), each independently, in whatever order operational need dictates — no connector depends on another.

**Backward compatibility:** Sprint 1's Configuration System already anticipated `credential_reference` (`CONFIGURATION_SYSTEM.md § 6` predates this package); no configuration schema migration is required for anything already deployed. Sprint 2's artifact envelope already carries every field the Knowledge Graph needs; no data migration is required for any already-validated artifact.

---

**End of package.** No implementation, stub, or code accompanies this document. No file outside this package was modified. Nothing has been committed. Awaiting architecture review and approval before any Sprint 3 implementation begins.
