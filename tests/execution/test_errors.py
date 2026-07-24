"""Tests for the Execution Engine's exception hierarchy
(Sprint 5 Architecture Package §16.1, as corrected by Review Comment 3's
narrowing of PlanNotExecutableError)."""

from __future__ import annotations

import pytest

from execution.errors import (
    ConfirmationDeniedError,
    ExecutionCancelledError,
    ExecutionError_,
    PlanNotExecutableError,
    RetryExhaustedError,
    RollbackError,
    StepExecutionError,
)

_SUBTYPES = (
    PlanNotExecutableError,
    ConfirmationDeniedError,
    StepExecutionError,
    RetryExhaustedError,
    ExecutionCancelledError,
    RollbackError,
)


def test_execution_error_base_is_an_exception() -> None:
    assert issubclass(ExecutionError_, Exception)


@pytest.mark.parametrize("error_type", _SUBTYPES)
def test_every_subtype_is_an_execution_error(error_type: type[Exception]) -> None:
    assert issubclass(error_type, ExecutionError_)


@pytest.mark.parametrize("error_type", _SUBTYPES)
def test_every_subtype_can_be_raised_and_caught_as_the_base(error_type: type[Exception]) -> None:
    with pytest.raises(ExecutionError_):
        raise error_type("boom")


@pytest.mark.parametrize("error_type", _SUBTYPES)
def test_every_subtype_carries_its_message(error_type: type[Exception]) -> None:
    try:
        raise error_type("something specific went wrong")
    except ExecutionError_ as exc:
        assert str(exc) == "something specific went wrong"


def test_execution_error_hierarchy_does_not_inherit_from_other_packages_errors() -> None:
    import integration.errors as integration_errors
    import planning.errors as planning_errors
    import runtime.errors as runtime_errors

    assert not issubclass(ExecutionError_, runtime_errors.RuntimeError_)
    assert not issubclass(ExecutionError_, integration_errors.IntegrationError_)
    assert not issubclass(ExecutionError_, planning_errors.PlanningError_)


def test_plan_not_executable_error_is_distinct_from_container_capability_resolution_error() -> None:
    from runtime.errors import CapabilityResolutionError

    assert not issubclass(PlanNotExecutableError, CapabilityResolutionError)
    assert not issubclass(CapabilityResolutionError, PlanNotExecutableError)
