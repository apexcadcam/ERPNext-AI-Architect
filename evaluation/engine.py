"""Architecture Evaluation's own stage logic.

Implements Architecture Evaluation Engine Specification v1.0 §4 exactly:
three deterministic stages, zero Reasoning Engine calls, zero filesystem
access.

`execute_rules`, `assemble_evaluation`, and `evaluate_architecture` are
package-internal-shared, used identically by `evaluation.module`'s own
Container-registered stage wrappers -- no duplicated stage logic between
the plain-function interface and the Pipeline-Engine-driven one.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from synthesis.contract import RepositoryFacts

from evaluation.contract import (
    ArchitectureEvaluation,
    EvaluationRequest,
    EvaluationStatistics,
    Finding,
    Severity,
    SkippedRule,
)
from evaluation.rules import ALL_RULES, FactIndex, build_fact_index


@dataclass
class Budget:
    """Shared, mutable budget threaded through rule execution -- mirrors
    `discovery.engine.walk_tree`'s/`synthesis.engine.Budget`'s own model,
    applied across rule executions rather than file reads (§7). Per §2's
    own contract, `max_findings` caps the *number of rules evaluated*, not
    literally "number of findings produced" -- the field name is inherited
    unmodified from the frozen specification.
    """

    remaining_rules: int
    deadline: float
    truncated: bool = field(default=False)

    def consume(self) -> bool:
        if self.remaining_rules <= 0 or time.monotonic() > self.deadline:
            self.truncated = True
            return False
        self.remaining_rules -= 1
        return True


# -- Stage 2: Rule Execution --------------------------------------------------------------------------


def execute_rules(
    facts: RepositoryFacts, index: FactIndex, budget: Budget | None = None
) -> tuple[tuple[Finding, ...], tuple[SkippedRule, ...]]:
    """Runs every registered rule, in fixed `rule_id` order, against the
    indexed facts. A rule's own algorithm raising unexpectedly is caught
    and recorded as a `SkippedRule` -- never aborts the run (§4, §7).
    """

    findings: list[Finding] = []
    skipped: list[SkippedRule] = []

    for rule_id, rule_fn in ALL_RULES:
        if budget is not None and not budget.consume():
            break
        try:
            result = rule_fn(facts, index)
        except Exception as exc:  # a raising rule is recorded, never propagated
            skipped.append(SkippedRule(rule_id=rule_id, reason=str(exc)))
            continue
        if result is not None:
            findings.append(result)

    return tuple(findings), tuple(skipped)


# -- Stage 3: Evaluation Assembly ----------------------------------------------------------------------


def assemble_evaluation(
    request: EvaluationRequest,
    findings: tuple[Finding, ...],
    skipped_rules: tuple[SkippedRule, ...],
    budget: Budget,
) -> ArchitectureEvaluation:
    by_severity: dict[Severity, int] = {}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

    statistics = EvaluationStatistics(
        rules_evaluated=request.max_findings - budget.remaining_rules,
        rules_skipped=len(skipped_rules),
        findings_produced=len(findings),
        findings_by_severity=by_severity,
    )
    return ArchitectureEvaluation(
        evaluation_id=str(uuid.uuid4()),
        source_facts_id=request.repository_facts.facts_id,
        repository_root=request.repository_facts.repository_root,
        evaluated_at=datetime.now(UTC).isoformat(),
        correlation_id=request.correlation_id,
        findings=findings,
        skipped_rules=skipped_rules,
        truncated=request.repository_facts.truncated or budget.truncated,
        statistics=statistics,
    )


# -- §2's public interface: the plain-function composition of all three stages -----------------------


def evaluate_architecture(request: EvaluationRequest) -> ArchitectureEvaluation:
    """The single, plain-function composition of all three stages — §2's
    first interface: no Container, no Module, no Pipeline Engine required.
    """

    facts = request.repository_facts
    index = build_fact_index(facts)
    budget = Budget(remaining_rules=request.max_findings, deadline=time.monotonic() + request.timeout_seconds)
    findings, skipped_rules = execute_rules(facts, index, budget)
    return assemble_evaluation(request, findings, skipped_rules, budget)
