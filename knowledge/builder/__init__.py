"""The deterministic Knowledge Builder — Sprint 10, Phase 2.

Transforms `analysis.contract.AnalysisResult` into `knowledge.domain`
contracts. No persistence, no indexing, no querying, no graph
implementation, no AI, no heuristics, no similarity logic. See
`builder.py`'s own module docstring for the fact-kind-by-fact-kind
compatibility findings that shaped this module's behavior.
"""

from __future__ import annotations

from knowledge.builder.builder import (
    build_actor_references,
    build_constraint_references,
    build_entity_references,
    build_knowledge_collection,
    build_knowledge_snapshot,
    build_process_references,
    build_rule_references,
    build_workflow_artifacts,
)

__all__ = [
    "build_actor_references",
    "build_constraint_references",
    "build_entity_references",
    "build_knowledge_collection",
    "build_knowledge_snapshot",
    "build_process_references",
    "build_rule_references",
    "build_workflow_artifacts",
]
