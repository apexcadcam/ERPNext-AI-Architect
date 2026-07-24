"""Tests for the Planning Engine's Phase 1 data models
(approved Sprint 4 Architecture Package §5.1, §5.3, §5.4, §5.5, §5.6).

No runtime behavior is tested because none exists yet in this phase —
construction, immutability, equality, hashability, and serialization only.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planning.contract import CapabilityDescriptor, Goal, Plan, PlanStep, RuntimeContextInfo

# -- Goal --------------------------------------------------------------------------


def test_goal_constructs_with_only_required_fields() -> None:
    goal = Goal(goal_id="G-0001", intent="do the thing")
    assert goal.goal_id == "G-0001"
    assert goal.intent == "do the thing"
    assert goal.desired_capabilities == ()
    assert goal.context_refs == ()
    assert goal.constraints == ()


def test_goal_constructs_with_every_field() -> None:
    goal = Goal(
        goal_id="G-0001",
        intent="do the thing",
        desired_capabilities=("filesystem.write_text",),
        context_refs=("KA-0001",),
        constraints=("no destructive writes",),
    )
    assert goal.desired_capabilities == ("filesystem.write_text",)
    assert goal.context_refs == ("KA-0001",)
    assert goal.constraints == ("no destructive writes",)


def test_goal_empty_goal_id_raises() -> None:
    with pytest.raises(ValidationError):
        Goal(goal_id="", intent="do the thing")


def test_goal_empty_intent_raises() -> None:
    with pytest.raises(ValidationError):
        Goal(goal_id="G-0001", intent="")


def test_goal_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        Goal(goal_id="G-0001")  # type: ignore[call-arg]


def test_goal_is_frozen() -> None:
    goal = Goal(goal_id="G-0001", intent="do the thing")
    with pytest.raises(ValidationError):
        goal.intent = "something else"


def test_goal_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Goal(goal_id="G-0001", intent="do the thing", nonsense="x")  # type: ignore[call-arg]


def test_goal_equality_is_value_based() -> None:
    a = Goal(goal_id="G-0001", intent="do the thing")
    b = Goal(goal_id="G-0001", intent="do the thing")
    assert a == b
    assert a is not b


def test_goal_is_hashable_and_equal_instances_hash_equal() -> None:
    a = Goal(goal_id="G-0001", intent="do the thing", desired_capabilities=("x",))
    b = Goal(goal_id="G-0001", intent="do the thing", desired_capabilities=("x",))
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_goal_serialization_round_trips() -> None:
    goal = Goal(goal_id="G-0001", intent="do the thing", desired_capabilities=("x", "y"))
    restored = Goal.model_validate_json(goal.model_dump_json())
    assert restored == goal


# -- RuntimeContextInfo -------------------------------------------------------------


def test_runtime_context_info_constructs() -> None:
    info = RuntimeContextInfo(environment="Production", requested_by="agent-1")
    assert info.environment == "Production"
    assert info.requested_by == "agent-1"


def test_runtime_context_info_empty_environment_raises() -> None:
    with pytest.raises(ValidationError):
        RuntimeContextInfo(environment="", requested_by="agent-1")


def test_runtime_context_info_is_frozen() -> None:
    info = RuntimeContextInfo(environment="Production", requested_by="agent-1")
    with pytest.raises(ValidationError):
        info.environment = "Development"


def test_runtime_context_info_is_hashable() -> None:
    a = RuntimeContextInfo(environment="Production", requested_by="agent-1")
    b = RuntimeContextInfo(environment="Production", requested_by="agent-1")
    assert hash(a) == hash(b)


def test_runtime_context_info_serialization_round_trips() -> None:
    info = RuntimeContextInfo(environment="Production", requested_by="agent-1")
    restored = RuntimeContextInfo.model_validate_json(info.model_dump_json())
    assert restored == info


# -- CapabilityDescriptor -----------------------------------------------------------


def test_capability_descriptor_constructs() -> None:
    descriptor = CapabilityDescriptor(
        capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
    )
    assert descriptor.capability == "filesystem.write_text"
    assert descriptor.kind == "write"


def test_capability_descriptor_invalid_kind_raises() -> None:
    with pytest.raises(ValidationError):
        CapabilityDescriptor(
            capability="filesystem.write_text",
            kind="delete",  # type: ignore[arg-type]
            idempotent=False,
            requires_confirmation=True,
        )


def test_capability_descriptor_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        CapabilityDescriptor(capability="filesystem.read_text", kind="read", idempotent=True)  # type: ignore[call-arg]


def test_capability_descriptor_is_frozen() -> None:
    descriptor = CapabilityDescriptor(
        capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
    )
    with pytest.raises(ValidationError):
        descriptor.requires_confirmation = True


def test_capability_descriptor_is_hashable() -> None:
    a = CapabilityDescriptor(
        capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
    )
    b = CapabilityDescriptor(
        capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
    )
    assert hash(a) == hash(b)


def test_capability_descriptor_serialization_round_trips() -> None:
    descriptor = CapabilityDescriptor(
        capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
    )
    restored = CapabilityDescriptor.model_validate_json(descriptor.model_dump_json())
    assert restored == descriptor


# -- PlanStep ------------------------------------------------------------------------


def test_plan_step_constructs_with_only_required_fields() -> None:
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    assert step.parameters == {}
    assert step.depends_on == ()
    assert step.rationale == ""


def test_plan_step_constructs_with_every_field() -> None:
    step = PlanStep(
        step_id="S-2",
        capability="filesystem.write_text",
        parameters={"path": "a.txt", "content": "hi"},
        depends_on=("S-1",),
        rationale="write after reading",
        requires_confirmation=True,
    )
    assert step.parameters == {"path": "a.txt", "content": "hi"}
    assert step.depends_on == ("S-1",)
    assert step.requires_confirmation is True


def test_plan_step_missing_requires_confirmation_raises() -> None:
    with pytest.raises(ValidationError):
        PlanStep(step_id="S-1", capability="filesystem.read_text")  # type: ignore[call-arg]


def test_plan_step_empty_step_id_raises() -> None:
    with pytest.raises(ValidationError):
        PlanStep(step_id="", capability="filesystem.read_text", requires_confirmation=False)


def test_plan_step_is_frozen_at_the_attribute_level() -> None:
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    with pytest.raises(ValidationError):
        step.step_id = "S-2"


def test_plan_step_parameters_dict_is_only_shallowly_immutable() -> None:
    # Disclosed, deliberate consequence of reusing Event.payload's own
    # dict[str, Any] shape (see contract.py's PlanStep docstring): the
    # attribute itself cannot be reassigned, but the dict it points to can
    # still be mutated in place. Locked in here as documented behavior,
    # not silently assumed.
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    step.parameters["path"] = "mutated.txt"
    assert step.parameters == {"path": "mutated.txt"}


def test_plan_step_is_not_hashable() -> None:
    # dict is categorically unhashable in Python — this holds even when
    # parameters is empty, per contract.py's own disclosed reasoning.
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    with pytest.raises(TypeError):
        hash(step)


def test_plan_step_serialization_round_trips() -> None:
    step = PlanStep(
        step_id="S-1",
        capability="filesystem.write_text",
        parameters={"path": "a.txt"},
        depends_on=("S-0",),
        requires_confirmation=True,
    )
    restored = PlanStep.model_validate_json(step.model_dump_json())
    assert restored == step


# -- Plan ----------------------------------------------------------------------------


def test_plan_constructs_with_zero_steps() -> None:
    plan = Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z", strategy_name="reference")
    assert plan.steps == ()


def test_plan_constructs_with_steps() -> None:
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(step,),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="reference",
    )
    assert plan.steps == (step,)


def test_plan_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z")  # type: ignore[call-arg]


def test_plan_is_frozen() -> None:
    plan = Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z", strategy_name="reference")
    with pytest.raises(ValidationError):
        plan.strategy_name = "other"


def test_plan_with_zero_steps_is_hashable() -> None:
    a = Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z", strategy_name="reference")
    b = Plan(plan_id="P-1", goal_id="G-1", created_at="2026-01-01T00:00:00Z", strategy_name="reference")
    assert hash(a) == hash(b)


def test_plan_with_any_step_is_not_hashable() -> None:
    # Inherits PlanStep's unhashability transitively — disclosed in
    # contract.py's PlanStep docstring.
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(step,),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="reference",
    )
    with pytest.raises(TypeError):
        hash(plan)


def test_plan_equality_is_value_based() -> None:
    step = PlanStep(step_id="S-1", capability="filesystem.read_text", requires_confirmation=False)
    a = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(step,),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="reference",
    )
    b = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(step,),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="reference",
    )
    assert a == b
    assert a is not b


def test_plan_serialization_round_trips() -> None:
    step = PlanStep(
        step_id="S-1",
        capability="filesystem.write_text",
        parameters={"path": "a.txt"},
        requires_confirmation=True,
    )
    plan = Plan(
        plan_id="P-1",
        goal_id="G-1",
        steps=(step,),
        created_at="2026-01-01T00:00:00Z",
        strategy_name="reference",
    )
    restored = Plan.model_validate_json(plan.model_dump_json())
    assert restored == plan


# -- No planning/validation/execution behavior exists yet ---------------------------


def test_plan_has_no_validation_or_execution_methods() -> None:
    # A structural guarantee this phase's own scope relies on: Plan/PlanStep
    # carry no behavior beyond ordinary pydantic model methods.
    plan_public_attrs = {name for name in dir(Plan) if not name.startswith("_")}
    forbidden = {"validate_plan", "execute", "run", "invoke"}
    assert plan_public_attrs.isdisjoint(forbidden)
