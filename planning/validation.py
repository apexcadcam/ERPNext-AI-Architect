"""Plan Validation: the single, uniform gate every candidate `Plan` passes
through, regardless of which `PlannerStrategy` (a later phase's concern —
not defined here) produced it.

Implements the approved Sprint 4 Architecture Package §6.3 exactly, its
five named rules:

  1. Every `PlanStep.capability` is present in
     `PlanningContext.available_capabilities`.
  2. Every `PlanStep.depends_on` entry names a `step_id` that exists within
     the same `Plan`.
  3. No dependency cycle exists among steps.
  4. A `Plan` with zero steps is valid — not a separate check: with no
     steps, rules 1/2/3/5 each trivially produce no violations.
  5. A step whose `capability` maps to a `CapabilityDescriptor` with
     `requires_confirmation=True` must itself carry
     `requires_confirmation=True`.

And its own `validate_plan(plan, context, *, raise_on_failure=True)` two-mode
public API (§4.4), mirroring `integration.registry.ConnectorRegistry.
validate(raise_on_failure=...)`'s identical shape — reused, not reinvented,
including `PlanValidationReport` mirroring `integration.registry.
ConnectorValidationReport`'s own "report every issue, not just the first"
discipline (never fail fast, per this phase's own requirement).

Pure and side-effect-free: no graph traversal (nothing here calls
`PlanningContext.graph`), no connector logic, no Runtime logic — every rule
is a deterministic function of `plan` and `context.available_capabilities`
alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planning.contract import CapabilityDescriptor, Plan, PlanStep
from planning.context import PlanningContext
from planning.errors import PlanValidationError


@dataclass
class PlanValidationReport:
    """The result of `validate_plan`, always fully computed (never
    short-circuited) so every violation can be reported at once — the same
    "report all, not just the first" discipline
    `integration.registry.ConnectorValidationReport` already establishes.
    """

    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def as_issues(self) -> list[str]:
        return list(self.violations)


def validate_plan(
    plan: Plan, context: PlanningContext, *, raise_on_failure: bool = True
) -> PlanValidationReport:
    """Runs every rule in §6.3 against `plan`, collecting every violation
    found. Raises `PlanValidationError` (carrying every violation) if
    `raise_on_failure` is `True` and the plan is invalid; otherwise always
    returns the report, valid or not.

    Deterministic: identical `(plan, context)` always produces an identical
    `PlanValidationReport.violations` list, in the same order — every rule
    below iterates `plan.steps`/`context.available_capabilities` (both
    fixed-order tuples) directly, never a set or an unordered structure.
    """

    report = PlanValidationReport()
    capabilities_by_name = _capabilities_by_name(context)
    known_step_ids = {step.step_id for step in plan.steps}

    report.violations.extend(_unknown_capability_violations(plan, capabilities_by_name))
    report.violations.extend(_unknown_dependency_violations(plan, known_step_ids))
    report.violations.extend(_dependency_cycle_violations(plan))
    report.violations.extend(_confirmation_understatement_violations(plan, capabilities_by_name))

    if raise_on_failure and not report.ok:
        formatted = "\n".join(f"  - {issue}" for issue in report.as_issues())
        raise PlanValidationError(f"plan '{plan.plan_id}' failed validation:\n{formatted}")

    return report


# -- Rule helpers (private — validate_plan is the sole public entry point) -----------


def _capabilities_by_name(context: PlanningContext) -> dict[str, CapabilityDescriptor]:
    return {descriptor.capability: descriptor for descriptor in context.available_capabilities}


def _unknown_capability_violations(
    plan: Plan, capabilities_by_name: dict[str, CapabilityDescriptor]
) -> list[str]:
    """§6.3 rule 1."""

    return [
        f"step '{step.step_id}' references unknown capability '{step.capability}'"
        for step in plan.steps
        if step.capability not in capabilities_by_name
    ]


def _unknown_dependency_violations(plan: Plan, known_step_ids: set[str]) -> list[str]:
    """§6.3 rule 2."""

    violations: list[str] = []
    for step in plan.steps:
        for dependency_id in step.depends_on:
            if dependency_id not in known_step_ids:
                violations.append(f"step '{step.step_id}' depends_on unknown step '{dependency_id}'")
    return violations


def _dependency_cycle_violations(plan: Plan) -> list[str]:
    """§6.3 rule 3 — the same "rejected at validation time, not merely
    detected later" discipline `KNOWLEDGE_GRAPH_SPEC.md §3` already
    established for graph `depends_on` edges, reused for plan-step
    dependencies.
    """

    steps_by_id = {step.step_id: step for step in plan.steps}
    return [
        f"dependency cycle detected: {' -> '.join(cycle)}" for cycle in _find_dependency_cycles(steps_by_id)
    ]


def _confirmation_understatement_violations(
    plan: Plan, capabilities_by_name: dict[str, CapabilityDescriptor]
) -> list[str]:
    """§6.3 rule 5. Skips a step whose capability is unknown — rule 1
    already reports that separately; there is no descriptor to compare
    against.
    """

    violations: list[str] = []
    for step in plan.steps:
        descriptor = capabilities_by_name.get(step.capability)
        if descriptor is not None and descriptor.requires_confirmation and not step.requires_confirmation:
            violations.append(
                f"step '{step.step_id}' understates requires_confirmation for capability "
                f"'{step.capability}' (the capability requires confirmation, the step does not)"
            )
    return violations


def _find_dependency_cycles(steps_by_id: dict[str, PlanStep]) -> list[tuple[str, ...]]:
    """Every distinct dependency cycle among `steps_by_id`'s `depends_on`
    edges, each as an ordered tuple of step_ids from where the cycle was
    entered back to itself. A `depends_on` reference to a step outside
    `steps_by_id` is ignored here — rule 2's concern, not this one's.

    Standard three-color (white/gray/black) DFS cycle detection; iterates
    `steps_by_id` in its own (insertion, i.e. `plan.steps`) order, so
    results are deterministic for a given `Plan`.
    """

    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(steps_by_id, white)
    cycles: list[tuple[str, ...]] = []
    path: list[str] = []

    def visit(step_id: str) -> None:
        color[step_id] = gray
        path.append(step_id)
        for dependency_id in steps_by_id[step_id].depends_on:
            if dependency_id not in steps_by_id:
                continue
            if color[dependency_id] == gray:
                cycle_start = path.index(dependency_id)
                cycles.append((*path[cycle_start:], dependency_id))
            elif color[dependency_id] == white:
                visit(dependency_id)
        path.pop()
        color[step_id] = black

    for step_id in steps_by_id:
        if color[step_id] == white:
            visit(step_id)

    return cycles
