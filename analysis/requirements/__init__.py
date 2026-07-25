"""Deterministic Requirement Analysis — Sprint 9, Phase 3.

Converts already-structured requirement input (`raw.py`) into
`analysis.contract` objects (`analyzer.py`) — facts only, no LLM, no
inference beyond what the raw input already states, no ranking, no
recommendation, no similarity analysis, no Runtime integration, no
pipeline. See `analyzer.py`'s own module docstring for the identifier
scheme and mapping decisions.
"""

from __future__ import annotations

from analysis.requirements.analyzer import (
    analyze_actors,
    analyze_business_constraints,
    analyze_business_entities,
    analyze_business_processes,
    analyze_business_rules,
    analyze_requirement_statement,
    build_analysis_result,
    build_requirement_analysis,
)
from analysis.requirements.raw import (
    RawActorMention,
    RawConstraintMention,
    RawEntityMention,
    RawProcessMention,
    RawRequirement,
    RawRuleMention,
)

__all__ = [
    "RawActorMention",
    "RawConstraintMention",
    "RawEntityMention",
    "RawProcessMention",
    "RawRequirement",
    "RawRuleMention",
    "analyze_actors",
    "analyze_business_constraints",
    "analyze_business_entities",
    "analyze_business_processes",
    "analyze_business_rules",
    "analyze_requirement_statement",
    "build_analysis_result",
    "build_requirement_analysis",
]
