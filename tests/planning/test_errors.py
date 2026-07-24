"""Tests for the Planning Engine's exception hierarchy
(approved Sprint 4 Architecture Package §7.1)."""

from __future__ import annotations

import pytest

from planning.errors import (
    GoalDefinitionError,
    NoUsableCapabilityError,
    PlanningContextError,
    PlanningError_,
    PlannerStrategyError,
    PlanValidationError,
)

_SUBTYPES = (
    GoalDefinitionError,
    PlanningContextError,
    NoUsableCapabilityError,
    PlannerStrategyError,
    PlanValidationError,
)


def test_planning_error_base_is_an_exception() -> None:
    assert issubclass(PlanningError_, Exception)


@pytest.mark.parametrize("error_type", _SUBTYPES)
def test_every_subtype_is_a_planning_error(error_type: type[Exception]) -> None:
    assert issubclass(error_type, PlanningError_)


@pytest.mark.parametrize("error_type", _SUBTYPES)
def test_every_subtype_can_be_raised_and_caught_as_the_base(error_type: type[Exception]) -> None:
    with pytest.raises(PlanningError_):
        raise error_type("boom")


@pytest.mark.parametrize("error_type", _SUBTYPES)
def test_every_subtype_carries_its_message(error_type: type[Exception]) -> None:
    try:
        raise error_type("something specific went wrong")
    except PlanningError_ as exc:
        assert str(exc) == "something specific went wrong"


def test_planning_error_hierarchy_does_not_inherit_from_other_packages_errors() -> None:
    # This project's established discipline (integration/errors.py,
    # secrets_management/errors.py): each package owns its own narrow
    # exception hierarchy rather than overloading another package's.
    import integration.errors as integration_errors
    import runtime.errors as runtime_errors
    import secrets_management.errors as secrets_errors

    assert not issubclass(PlanningError_, runtime_errors.RuntimeError_)
    assert not issubclass(PlanningError_, integration_errors.IntegrationError_)
    assert not issubclass(PlanningError_, secrets_errors.SecretResolutionError)


def test_no_usable_capability_error_is_distinct_from_container_capability_resolution_error() -> None:
    from runtime.errors import CapabilityResolutionError

    assert not issubclass(NoUsableCapabilityError, CapabilityResolutionError)
    assert not issubclass(CapabilityResolutionError, NoUsableCapabilityError)
