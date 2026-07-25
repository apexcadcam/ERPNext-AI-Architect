"""Deterministic Similarity Analysis — Sprint 9, Phase 4.

Compares any two same-typed tuples of `analysis.contract` objects
(`BusinessEntity`, `BusinessProcess`, `Actor`, `BusinessRule`,
`BusinessConstraint`) via a lexical Jaccard-token-overlap score — no
inference, no semantic AI, no embeddings, no vector search, no LLM. See
`comparator.py`'s own module docstring for the full algorithm, the gap
threshold, and disclosed content-scope notes.
"""

from __future__ import annotations

from analysis.similarity.comparator import (
    compare_actors,
    compare_analysis_result,
    compare_business_constraints,
    compare_business_entities,
    compare_business_processes,
    compare_business_rules,
    detect_actor_gaps,
    detect_business_constraint_gaps,
    detect_business_entity_gaps,
    detect_business_process_gaps,
    detect_business_rule_gaps,
)

__all__ = [
    "compare_actors",
    "compare_analysis_result",
    "compare_business_constraints",
    "compare_business_entities",
    "compare_business_processes",
    "compare_business_rules",
    "detect_actor_gaps",
    "detect_business_constraint_gaps",
    "detect_business_entity_gaps",
    "detect_business_process_gaps",
    "detect_business_rule_gaps",
]
