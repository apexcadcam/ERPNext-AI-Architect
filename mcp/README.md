# mcp/

## Purpose

**Phase 4 — not yet active.** This folder exists now so the repository's intended shape is visible from day one, per the mandatory order in [ROADMAP.md](../ROADMAP.md): Research → Rules → Skills → Agents → MCP. It stays empty until an agent in [`agents/`](../agents/) actually needs to execute something against a live bench.

## What belongs inside (once active)

Tool/server definitions for mechanical actions only — reading a file, running a bench command, querying a doctype. Execution, not decisions.

## What does NOT belong inside

Any architectural judgment. MCP only executes what an agent, built from skills, built from rules, has already decided to do — it never decides anything itself.

## Typical lifecycle

Created only once a concrete, repeated execution need shows up from an active agent → implemented → deprecated when no longer called by any agent.
