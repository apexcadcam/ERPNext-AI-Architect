"""Tests for `PlanningContext` (approved Sprint 4 Architecture Package §5.2).

No planning behavior is tested here — `PlanningContext` is pure, frozen
data; nothing in this phase constructs one for any purpose beyond proving
it can be constructed and is immutable.
"""

from __future__ import annotations

import pytest
from knowledge.graph import InMemoryGraphStore
from pydantic import ValidationError

from planning.contract import CapabilityDescriptor, RuntimeContextInfo
from planning.context import PlanningContext
from planning.graph_reader import GraphReader


@pytest.fixture
def runtime_context() -> RuntimeContextInfo:
    return RuntimeContextInfo(environment="Development", requested_by="test-suite")


def test_planning_context_constructs_with_a_real_graph_store(runtime_context: RuntimeContextInfo) -> None:
    store = InMemoryGraphStore()
    context = PlanningContext(graph=store, runtime_context=runtime_context, correlation_id="corr-1")
    assert context.graph is store
    assert context.available_capabilities == ()
    assert context.correlation_id == "corr-1"


def test_planning_context_graph_field_is_typed_as_graph_reader(runtime_context: RuntimeContextInfo) -> None:
    store = InMemoryGraphStore()
    context = PlanningContext(graph=store, runtime_context=runtime_context, correlation_id="corr-1")
    assert isinstance(context.graph, GraphReader)


def test_planning_context_constructs_with_available_capabilities(runtime_context: RuntimeContextInfo) -> None:
    descriptor = CapabilityDescriptor(
        capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
    )
    context = PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(descriptor,),
        runtime_context=runtime_context,
        correlation_id="corr-1",
    )
    assert context.available_capabilities == (descriptor,)


def test_planning_context_missing_required_field_raises(runtime_context: RuntimeContextInfo) -> None:
    with pytest.raises(ValidationError):
        PlanningContext(runtime_context=runtime_context, correlation_id="corr-1")  # type: ignore[call-arg]


def test_planning_context_empty_correlation_id_raises(runtime_context: RuntimeContextInfo) -> None:
    with pytest.raises(ValidationError):
        PlanningContext(graph=InMemoryGraphStore(), runtime_context=runtime_context, correlation_id="")


def test_planning_context_rejects_unknown_fields(runtime_context: RuntimeContextInfo) -> None:
    with pytest.raises(ValidationError):
        PlanningContext(
            graph=InMemoryGraphStore(),
            runtime_context=runtime_context,
            correlation_id="corr-1",
            nonsense="x",  # type: ignore[call-arg]
        )


def test_planning_context_is_frozen(runtime_context: RuntimeContextInfo) -> None:
    context = PlanningContext(
        graph=InMemoryGraphStore(), runtime_context=runtime_context, correlation_id="corr-1"
    )
    with pytest.raises(ValidationError):
        context.correlation_id = "corr-2"


def test_planning_context_has_no_methods_beyond_ordinary_model_behavior(
    runtime_context: RuntimeContextInfo,
) -> None:
    public_attrs = {name for name in dir(PlanningContext) if not name.startswith("_")}
    forbidden = {"resolve_capabilities", "create_plan", "traverse_graph"}
    assert public_attrs.isdisjoint(forbidden)
