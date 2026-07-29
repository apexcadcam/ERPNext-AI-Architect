# ROADMAP

## Milestone: Architecture Freeze v1.0

**Phase 1 — Repository Foundation is complete.** See [PROJECT_CHARTER.md § Architecture Freeze v1.0](PROJECT_CHARTER.md#architecture-freeze-v10) for the full declaration. Completed:

- ✅ Repository Architecture — [ENGINEERING_META_MODEL.md](ENGINEERING_META_MODEL.md)
- ✅ Research Framework — [research/RESEARCH_FRAMEWORK.md](research/RESEARCH_FRAMEWORK.md)
- ✅ Engineering Rule Model — the `Engineering Rule` artifact type in [ENGINEERING_META_MODEL.md](ENGINEERING_META_MODEL.md)
- ✅ Engineering Rule Specification — [docs/ENGINEERING_RULE_SPECIFICATION.md](docs/ENGINEERING_RULE_SPECIFICATION.md)
- ✅ Engineering Rule Template — [templates/ENGINEERING_RULE_TEMPLATE.md](templates/ENGINEERING_RULE_TEMPLATE.md)
- ✅ Legacy Rule Migration — all ten founding rules (`R001`–`R010`) now follow the canonical format

Architecture work is now considered complete unless practical usage surfaces a genuine structural deficiency — not because a cleaner idea exists. See [PROJECT_CHARTER.md's Design Principles](PROJECT_CHARTER.md#design-principles). The repository now enters **Phase 2 — Knowledge Engineering**, below.

---

# Phase 2 — Knowledge Engineering

**Status: Active.** This is the repository's steady state, not a step with an end date — it continues for as long as the project does.

With the architecture frozen, the repository's job is no longer to figure out *how* knowledge should be structured — that's decided. The job now is to *produce* it: real Research, real Engineering Rules, and eventually real Skills and Agents, using the pipeline Phase 1 built:

```
Research → Engineering Rule → Skill → Agent
```

This is the same pipeline broken out stage-by-stage below — Phase 2 is what running it, continuously, actually looks like. Architecture changes during this phase are the exception, triggered only by a genuine structural gap the frozen model can't express — never by a theoretically better design arriving unprompted (per the Architecture Freeze declaration above).

## Pipeline stages

Each stage remains a *precondition* for the next — this ordering is part of the frozen architecture and is unchanged by this milestone. Skipping ahead produces exactly the failure mode [PROJECT_CHARTER.md](PROJECT_CHARTER.md) and [ENGINEERING_META_MODEL.md](ENGINEERING_META_MODEL.md) exist to prevent: judgment encoded somewhere other than a Rule, invisible and unaudited.

### Stage 1 — Research + Engineering Rules

**Folders:** [research/](research/), [rules/](rules/), [knowledge-sources/](knowledge-sources/)

The [ERPNext Knowledge Source Catalog](knowledge-sources/KNOWLEDGE_SOURCE_CATALOG.md) identifies and scores every external source Research may draw evidence from — it is an input to this stage, not a stage of its own; no knowledge has been extracted from it yet. The [Knowledge Acquisition Architecture](docs/knowledge-pipeline/KNOWLEDGE_ACQUISITION_ARCHITECTURE.md) designs, but does not implement, the pipeline that would eventually turn that catalog into structured knowledge, and the [Crawler Framework Architecture](docs/crawler/CRAWLER_ARCHITECTURE.md) designs, but does not implement, the modular, plugin-based system that would realize that pipeline's Acquisition stage for hundreds of source connectors. The [Runtime Architecture](docs/runtime/RUNTIME_ARCHITECTURE.md) designs — and, unlike the two above, **now implements** — the domain-agnostic execution substrate (module system, plugin registry, pipeline engine, event bus, DI) that the Crawler and every future module would plug into; see `runtime/`. Built on it, the [Evidence Platform](docs/evidence-platform/README.md) is the first component that actually produces evidence at scale: it extracts verifiable facts from pinned checkouts of `frappe` and `erpnext` and aggregates them into measured Patterns, each traceable to a file and line. It does not yet feed Stage 1 automatically — turning a measured Pattern into a Candidate Rule is its own later, separately-scoped work — but it is where the evidence a future Rule cites will come from. The [AI Architect Studio](docs/studio/STUDIO_ARCHITECTURE.md) designs, but does not implement, the permanent, purely-observational module that would make all of the above visible in real time, built entirely from Event Bus subscriptions. Building any of this is future, separately-scoped work, gated by its own Architecture Review per [ADR-0002](adr/ADR-0002-knowledge-pipeline-artifact-reconciliation.md).

Nothing gets built before it's understood. `research/` holds open questions about how ERPNext/Frappe actually behaves; once a question is answered with enough confidence and evidence, it becomes a Rule in `rules/`. **Active** — this stage never "completes"; it's the ongoing engine of Phase 2.

**Why it comes first:** every later stage — a Skill, an Agent, an MCP Tool — is a packaging of judgment that has to already exist somewhere. If that judgment isn't first written down as a Rule, it gets invented ad hoc at whatever layer needs it, which is exactly how untraceable, contradictory knowledge accumulates.

### Stage 2 — Skills

**Folder:** [skills/](skills/)

Once `rules/` has enough proven, stable rules covering a recurring task end to end, that task gets packaged as a Skill — a repeatable procedure that applies the relevant rules in order. **Not yet started.**

**Why it depends on Stage 1:** a Skill with no underlying Rule is undocumented judgment wearing a procedure's clothing. Skills are only allowed to *compose* existing rules, never to introduce new architectural opinions of their own.

### Stage 3 — AI Agents

**Folder:** [agents/](agents/)

Once several Skills exist, related ones get composed into an Agent — a persona capable of carrying out broader work by sequencing multiple Skills. **Not yet started.**

**Why it depends on Stage 2:** an Agent is only as trustworthy as the Skills it's built from. Composing Skills that don't exist yet just means the Agent is improvising — which reintroduces the exact problem Stage 1 and 2 exist to remove.

### Stage 4 — MCP Tools

**Folder:** [mcp/](mcp/)

Once an Agent needs to actually *do* something against a live bench (read a file, run a command, query a doctype), it's given an MCP Tool to execute that mechanical step. **Not yet started.**

**Why it depends on Stage 3:** MCP Tools carry no judgment of their own — they only execute. Building one before an Agent exists to call it means building execution capability with no defined caller and no rule dictating when it should be used.

## Supporting folders (not a stage — used throughout)

- **[templates/](templates/)** — implementation scaffolds, added opportunistically once a rule or pattern has proven itself in practice more than once. Not tied to one stage.
- **[adr/](adr/)** — records of non-obvious decisions about this repository's own structure or process. Used whenever such a decision is made, in any stage — including any future architecture-review decision made under the Architecture Freeze policy above.
- **[anti-patterns/](anti-patterns/)** — named, recurring bad patterns referenced by rules. Grows alongside `rules/` in Stage 1, but is a cross-cutting reference, not a stage of its own.
- **[docs/ai-retrieval/](docs/ai-retrieval/)**, **[rules/metadata/](rules/metadata/)**, **[rules/index/](rules/index/)** — an AI retrieval metadata layer, added under [ADR-0001](adr/ADR-0001-ai-retrieval-metadata-layer.md) as the one exception the Architecture Freeze above anticipates: a genuine structural deficiency (no way to find/rank/relate rules at scale beyond reading all of them serially) rather than a redesign for its own sake. Fully additive — `rules/*.md` is untouched.

## Current status

**Phase 1 — Repository Foundation: complete.** **Phase 2 — Knowledge Engineering: active**, currently in Stage 1. `rules/` contains ten rules (`R001`–`R010`), all migrated to the canonical format. `research/` has produced its first research file ([RQ-0001](research/RQ-0001-native-first-discovery.md)) — see [research/README.md](research/README.md) for the ongoing backlog. Stages 2–4 have not started; their folders exist only so the intended shape of the repository is visible, per each folder's own README.

**Evidence Platform: released at `v1.3.0`.** Extraction, Aggregation, and the `architect` CLI are implemented, validated against both canonical repositories, and documented in [docs/evidence-platform/](docs/evidence-platform/). Next work item is **Sprint 22 — class-definition Evidence**, which closes the platform's one declared measurement gap; the full item list, with what "done" means for each, is in [docs/evidence-platform/BACKLOG.md](docs/evidence-platform/BACKLOG.md).
