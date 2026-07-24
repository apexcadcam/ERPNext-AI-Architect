"""Tests for Plan Validation (approved Sprint 4 Architecture Package §6.3).

No graph traversal, no connector logic, no PlanningEngine/PlannerStrategy —
`validate_plan` is exercised directly against hand-built `Plan`/
`PlanningContext` fixtures only.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from knowledge.graph import InMemoryGraphStore

from planning.contract import CapabilityDescriptor, Plan, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext
from planning.errors import PlanValidationError
from planning.validation import PlanValidationReport, validate_plan


@pytest.fixture
def read_capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
    )


@pytest.fixture
def write_capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
    )


@pytest.fixture
def make_context(
    read_capability: CapabilityDescriptor, write_capability: CapabilityDescriptor
) -> Callable[..., PlanningContext]:
    def _make(*, capabilities: tuple[CapabilityDescriptor, ...] | None = None) -> PlanningContext:
        return PlanningContext(
            graph=InMemoryGraphStore(),
            available_capabilities=capabilities
            if capabilities is not None
            else (read_capability, write_capability),
            runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
            correlation_id="corr-1",
        )

    return _make


def _plan(*steps: PlanStep) -> Plan:
    return Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=steps,
        created_at="2026-01-01T00:00:00Z",
        strategy_name="reference",
    )


# -- Valid plans ---------------------------------------------------------------------


def test_valid_single_step_plan_passes(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False))

    report = validate_plan(plan, make_context())

    assert report.ok
    assert report.violations == []


def test_valid_multi_step_plan_with_dependencies_passes(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(
        PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False),
        PlanStep(
            step_id="S-2",
            capability="filesystem.write_text",
            depends_on=("S-1",),
            requires_confirmation=True,
        ),
    )

    report = validate_plan(plan, make_context())

    assert report.ok


# -- Rule 1: unknown capability -------------------------------------------------------


def test_unknown_capability_is_a_violation(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="erpnext.write_record", requires_confirmation=False))

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert not report.ok
    assert any(
        "unknown capability" in issue and "erpnext.write_record" in issue for issue in report.violations
    )


# -- Rule 2: unknown dependency -------------------------------------------------------


def test_unknown_dependency_target_is_a_violation(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(
        PlanStep(
            step_id="S-1",
            capability="filesystem.read_text",
            depends_on=("S-does-not-exist",),
            requires_confirmation=False,
        )
    )

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert not report.ok
    assert any("unknown step" in issue and "S-does-not-exist" in issue for issue in report.violations)


# -- Rule 3: dependency cycles --------------------------------------------------------


def test_self_cycle_is_a_violation(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(
        PlanStep(
            step_id="S-1", capability="filesystem.read_text", depends_on=("S-1",), requires_confirmation=False
        )
    )

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert not report.ok
    assert any("cycle" in issue for issue in report.violations)


def test_multi_step_cycle_is_a_violation(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(
        PlanStep(
            step_id="S-1", capability="filesystem.read_text", depends_on=("S-2",), requires_confirmation=False
        ),
        PlanStep(
            step_id="S-2", capability="filesystem.read_text", depends_on=("S-3",), requires_confirmation=False
        ),
        PlanStep(
            step_id="S-3", capability="filesystem.read_text", depends_on=("S-1",), requires_confirmation=False
        ),
    )

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert not report.ok
    assert any("cycle" in issue for issue in report.violations)


def test_a_shared_dependency_is_not_mistaken_for_a_cycle(
    make_context: Callable[..., PlanningContext],
) -> None:
    # S-1 -> S-3 and S-2 -> S-3 (diamond shape) must not be rejected.
    plan = _plan(
        PlanStep(
            step_id="S-1", capability="filesystem.read_text", depends_on=("S-3",), requires_confirmation=False
        ),
        PlanStep(
            step_id="S-2", capability="filesystem.read_text", depends_on=("S-3",), requires_confirmation=False
        ),
        PlanStep(step_id="S-3", capability="filesystem.read_text", requires_confirmation=False),
    )

    report = validate_plan(plan, make_context())

    assert report.ok


# -- Rule 4: empty plans ---------------------------------------------------------------


def test_empty_plan_is_valid(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan()

    report = validate_plan(plan, make_context())

    assert report.ok
    assert report.violations == []


# -- Rule 5: confirmation understatement -----------------------------------------------


def test_confirmation_understatement_is_a_violation(make_context: Callable[..., PlanningContext]) -> None:
    # filesystem.write_text's descriptor requires confirmation; the step
    # claims it does not.
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.write_text", requires_confirmation=False))

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert not report.ok
    assert any("understates requires_confirmation" in issue for issue in report.violations)


def test_confirmation_correctly_stated_is_not_a_violation(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.write_text", requires_confirmation=True))

    report = validate_plan(plan, make_context())

    assert report.ok


def test_overstating_confirmation_is_not_a_violation(make_context: Callable[..., PlanningContext]) -> None:
    # A step may require confirmation even when its capability doesn't --
    # only *understating* is a violation, per §6.3 rule 5's own wording.
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=True))

    report = validate_plan(plan, make_context())

    assert report.ok


# -- Multiple simultaneous violations ---------------------------------------------------


def test_multiple_simultaneous_violations_are_all_collected(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(
        PlanStep(
            step_id="S-1",
            capability="erpnext.write_record",  # rule 1: unknown capability
            depends_on=("S-missing",),  # rule 2: unknown dependency
            requires_confirmation=False,
        ),
        PlanStep(
            step_id="S-2",
            capability="filesystem.write_text",  # rule 5: understates confirmation
            depends_on=("S-2",),  # rule 3: self-cycle
            requires_confirmation=False,
        ),
    )

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert not report.ok
    assert len(report.violations) == 4
    assert any("unknown capability" in v for v in report.violations)
    assert any("unknown step" in v for v in report.violations)
    assert any("cycle" in v for v in report.violations)
    assert any("understates requires_confirmation" in v for v in report.violations)


def test_never_fails_fast_all_rules_run_regardless_of_earlier_violations(
    make_context: Callable[..., PlanningContext],
) -> None:
    # Even though S-1 already violates rule 1, rule 5 must still be
    # evaluated for S-2 in the same plan.
    plan = _plan(
        PlanStep(step_id="S-1", capability="nonexistent.capability", requires_confirmation=False),
        PlanStep(step_id="S-2", capability="filesystem.write_text", requires_confirmation=False),
    )

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert len(report.violations) == 2


# -- raise_on_failure ------------------------------------------------------------------


def test_raise_on_failure_true_raises_plan_validation_error(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="unknown.capability", requires_confirmation=False))

    with pytest.raises(PlanValidationError):
        validate_plan(plan, make_context())  # raise_on_failure defaults to True


def test_raise_on_failure_true_error_message_lists_every_violation(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(
        PlanStep(step_id="S-1", capability="unknown.capability", requires_confirmation=False),
        PlanStep(
            step_id="S-2",
            capability="filesystem.read_text",
            depends_on=("S-missing",),
            requires_confirmation=False,
        ),
    )

    with pytest.raises(PlanValidationError) as excinfo:
        validate_plan(plan, make_context())

    assert "unknown capability" in str(excinfo.value)
    assert "unknown step" in str(excinfo.value)


def test_raise_on_failure_false_returns_the_report_instead_of_raising(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="unknown.capability", requires_confirmation=False))

    report = validate_plan(plan, make_context(), raise_on_failure=False)

    assert isinstance(report, PlanValidationReport)
    assert not report.ok


def test_raise_on_failure_true_does_not_raise_for_a_valid_plan(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False))

    report = validate_plan(plan, make_context())  # must not raise

    assert report.ok


# -- Determinism -------------------------------------------------------------------------


def test_validate_plan_is_deterministic(make_context: Callable[..., PlanningContext]) -> None:
    plan = _plan(
        PlanStep(step_id="S-1", capability="erpnext.write_record", requires_confirmation=False),
        PlanStep(
            step_id="S-2",
            capability="filesystem.write_text",
            depends_on=("S-1", "S-missing"),
            requires_confirmation=False,
        ),
    )
    context = make_context()

    first = validate_plan(plan, context, raise_on_failure=False)
    second = validate_plan(plan, context, raise_on_failure=False)

    assert first.violations == second.violations


# -- Purity / side-effect freedom ---------------------------------------------------------


def test_validate_plan_never_touches_the_graph(make_context: Callable[..., PlanningContext]) -> None:
    context = make_context()
    graph = context.graph
    assert isinstance(graph, InMemoryGraphStore)
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False))

    validate_plan(plan, context)

    assert graph.all_nodes() == ()  # nothing was ever written or read from the graph


def test_validate_plan_never_mutates_the_plan_or_context(
    make_context: Callable[..., PlanningContext],
) -> None:
    plan = _plan(PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False))
    context = make_context()
    plan_before = plan.model_copy(deep=True)
    context_before_capabilities = context.available_capabilities

    validate_plan(plan, context, raise_on_failure=False)

    assert plan == plan_before
    assert context.available_capabilities == context_before_capabilities
