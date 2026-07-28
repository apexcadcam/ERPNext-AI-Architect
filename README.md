# ERPNext AI Architect

**An engineering knowledge base for building AI-assisted, upgrade-safe Frappe/ERPNext applications — not an ERPNext app, and not a prompt library.**

This repository codifies the recurring, costly architectural mistakes made on real Frappe/ERPNext projects into explicit, falsifiable Engineering Rules, and defines how those rules turn into reusable Skills and, eventually, autonomous Agents — all traceable back to real evidence, none of it locked to a specific AI vendor or model.

## Start here

- **[PROJECT_CHARTER.md](PROJECT_CHARTER.md)** — why this repository exists, who it's for, and the principles every artifact must follow.
- **[AGENTS.md](AGENTS.md)** — mandatory operating instructions for any AI coding agent working in this repository.
- **[ENGINEERING_META_MODEL.md](ENGINEERING_META_MODEL.md)** — the full knowledge model: every artifact type this repository can contain and how they relate.
- **[ROADMAP.md](ROADMAP.md)** — current phase, what's active, what's next.

## Repository maturity

**Phase 1 — Repository Foundation.** *Complete.* Designing the architecture itself: the knowledge model, the research process, the canonical Engineering Rule specification and template, and migrating all ten founding rules (`R001`–`R010`) to that format. See [PROJECT_CHARTER.md § Architecture Freeze v1.0](PROJECT_CHARTER.md#architecture-freeze-v10).

**Phase 2 — Knowledge Engineering.** *Active.* With the architecture frozen, the repository's ongoing work is producing real engineering knowledge through the approved pipeline — Research → Engineering Rule → Skill → Agent — not redesigning how that pipeline works. See [ROADMAP.md](ROADMAP.md) for what's currently active.

> Prefer improving engineering knowledge over redesigning repository architecture.
> — [PROJECT_CHARTER.md, Design Principles](PROJECT_CHARTER.md#design-principles)

## The Evidence Platform

The knowledge in this repository is not produced by a language model. It is extracted from pinned checkouts of the canonical Frappe and ERPNext repositories, and every conclusion is traceable to the file and line it came from.

```bash
architect evidence extract erpnext --version v15.102.0 --commit 1d14ba16398db3a220873509565c60f2932bed81
architect patterns aggregate erpnext --version v15.102.0
architect patterns report erpnext --version v15.102.0
```

Extraction emits one record per single observed fact; aggregation turns those into measured Patterns — but only where a denominator genuinely exists. Where it does not, the platform records a typed, persisted skip stating exactly why, rather than quoting a ratio it cannot support.

Full design, current measurements, and known limits: **[docs/evidence-platform/](docs/evidence-platform/)** and the [Evidence Platform Release Notes](EVIDENCE_PLATFORM_RELEASE_NOTES.md).

## Repository layout

| Path | Contains |
|---|---|
| [`research/`](research/) | Open questions and investigations, following [RESEARCH_FRAMEWORK.md](research/RESEARCH_FRAMEWORK.md) |
| [`rules/`](rules/) | Engineering Rules — the source of truth (`R001`–`R010`) |
| [`docs/`](docs/) | Formal specifications, e.g. the [Engineering Rule Specification](docs/ENGINEERING_RULE_SPECIFICATION.md) |
| [`docs/ai-retrieval/`](docs/ai-retrieval/) | AI retrieval metadata layer — additive to `rules/`, never a replacement for it; see [ADR-0001](adr/ADR-0001-ai-retrieval-metadata-layer.md) |
| [`knowledge-sources/`](knowledge-sources/) | [ERPNext/Frappe Knowledge Source Catalog](knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) — every external source this project may draw on, evaluated and tiered. Sources only; no knowledge extracted yet. |
| [`docs/knowledge-pipeline/`](docs/knowledge-pipeline/) | [Knowledge Acquisition Architecture](docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) — the full source→acquisition→extraction→graph→embeddings→retrieval pipeline design. Architecture only; not implemented. |
| [`docs/crawler/`](docs/crawler/) | [Crawler Framework Architecture](docs/crawler/CRAWLER_ARCHITECTURE.md) — the modular, plugin-based crawling system that realizes the Knowledge Pipeline's Acquisition stage. Architecture only; not implemented. |
| [`docs/runtime/`](docs/runtime/) | [Runtime Architecture](docs/runtime/RUNTIME_ARCHITECTURE.md) — the domain-agnostic "operating system" (module system, plugin registry, pipeline engine, event bus, DI, storage abstraction, CLI) every module, including the Crawler, plugs into. **Implemented** — see `runtime/`. |
| [`docs/evidence-platform/`](docs/evidence-platform/) | [The Evidence Platform](docs/evidence-platform/README.md) — extraction of verifiable facts from canonical Frappe/ERPNext repositories, and their aggregation into measured Patterns. **Implemented** — see `evidence/`, `aggregation/`, and the `architect` CLI. |
| [`docs/studio/`](docs/studio/) | [AI Architect Studio Architecture](docs/studio/STUDIO_ARCHITECTURE.md) — a permanent, purely observational Runtime module: a real-time Engineering Intelligence Dashboard built entirely from Event Bus subscriptions, structurally incapable of controlling anything. Architecture only; not implemented. |
| [`rules/metadata/`](rules/metadata/), [`rules/index/`](rules/index/) | Derived, machine-generated retrieval records and index for the rules above — non-authoritative |
| [`templates/`](templates/) | Authoring templates and implementation scaffolds |
| [`skills/`](skills/), [`agents/`](agents/), [`mcp/`](mcp/) | Phase 2, stages 2–4 — not yet populated (see [ROADMAP.md](ROADMAP.md)) |
| [`adr/`](adr/) | Architecture Decision Records |
| [`anti-patterns/`](anti-patterns/) | Named, recurring bad patterns |

This repository is not a prompt collection — see [PROJECT_CHARTER.md § Repository Philosophy](PROJECT_CHARTER.md#repository-philosophy).
