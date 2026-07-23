"""Tests for the Dependency Injection Container (DEPENDENCY_INJECTION.md)."""

from __future__ import annotations

import pytest

from runtime.container.di import CapabilityScope, Container
from runtime.errors import CapabilityResolutionError


def test_singleton_capability_is_constructed_exactly_once() -> None:
    container = Container()
    call_count = 0

    def factory() -> object:
        nonlocal call_count
        call_count += 1
        return object()

    container.register("thing", factory)
    first = container.resolve("thing")
    second = container.resolve("thing")

    assert first is second
    assert call_count == 1


def test_resolving_an_unregistered_capability_raises() -> None:
    container = Container()
    with pytest.raises(CapabilityResolutionError):
        container.resolve("nothing.here")


def test_registering_the_same_capability_twice_without_override_raises() -> None:
    container = Container()
    container.register("thing", object)
    with pytest.raises(CapabilityResolutionError):
        container.register("thing", object)


def test_override_true_replaces_the_provider_for_test_doubles() -> None:
    container = Container()
    container.register("thing", lambda: "real")
    assert container.resolve("thing") == "real"

    container.register("thing", lambda: "fake", override=True)
    assert container.resolve("thing") == "fake"


def test_pipeline_run_scoped_capability_requires_a_scope_id() -> None:
    container = Container()
    container.register("ctx", object, scope=CapabilityScope.PIPELINE_RUN)
    with pytest.raises(CapabilityResolutionError):
        container.resolve("ctx")


def test_pipeline_run_scoped_capability_is_cached_per_scope_id() -> None:
    container = Container()
    container.register("ctx", object, scope=CapabilityScope.PIPELINE_RUN)

    a1 = container.resolve("ctx", scope_id="run-1")
    a2 = container.resolve("ctx", scope_id="run-1")
    b1 = container.resolve("ctx", scope_id="run-2")

    assert a1 is a2
    assert a1 is not b1


def test_close_scope_evicts_cached_instances_for_that_scope_only() -> None:
    container = Container()
    container.register("ctx", object, scope=CapabilityScope.PIPELINE_RUN)

    before = container.resolve("ctx", scope_id="run-1")
    kept = container.resolve("ctx", scope_id="run-2")
    container.close_scope(CapabilityScope.PIPELINE_RUN, "run-1")
    after = container.resolve("ctx", scope_id="run-1")
    still_kept = container.resolve("ctx", scope_id="run-2")

    assert before is not after
    assert kept is still_kept


def test_provided_capabilities_reflects_registrations() -> None:
    container = Container()
    container.register("a", object)
    container.register("b", object)
    assert container.provided_capabilities() == frozenset({"a", "b"})
