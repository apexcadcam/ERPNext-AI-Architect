"""Tests for the Pipeline Engine (docs/runtime/PIPELINE_ENGINE.md)."""

from __future__ import annotations

import time

import pytest

from runtime.container.di import Container
from runtime.errors import PipelineDefinitionError
from runtime.events.bus import EventBus
from runtime.lifecycle import PipelineRunState
from runtime.pipeline.engine import PipelineDefinition, PipelineEngine, StageDefinition, StageOutcome


def _success_stage(transform):
    return lambda: (lambda data, ctx: (transform(data), StageOutcome.SUCCESS))


def test_registering_a_pipeline_with_no_stages_raises() -> None:
    with pytest.raises(PipelineDefinitionError):
        PipelineDefinition(name="empty", stages=())


def test_registering_a_pipeline_with_duplicate_stage_names_raises() -> None:
    with pytest.raises(PipelineDefinitionError):
        PipelineDefinition(
            name="dup",
            stages=(
                StageDefinition(name="a", capability="cap.a"),
                StageDefinition(name="a", capability="cap.b"),
            ),
        )


def test_registering_the_same_pipeline_name_twice_raises() -> None:
    container = Container()
    container.register("cap.a", _success_stage(lambda d: d))
    engine = PipelineEngine(container)
    definition = PipelineDefinition(name="p", stages=(StageDefinition(name="a", capability="cap.a"),))
    engine.register(definition)
    with pytest.raises(PipelineDefinitionError):
        engine.register(definition)


def test_running_an_unregistered_pipeline_raises() -> None:
    engine = PipelineEngine(Container())
    with pytest.raises(PipelineDefinitionError):
        engine.run("nope")


def test_data_flows_sequentially_through_every_stage() -> None:
    container = Container()
    container.register("cap.double", _success_stage(lambda d: d * 2))
    container.register("cap.increment", _success_stage(lambda d: d + 1))
    engine = PipelineEngine(container)
    engine.register(
        PipelineDefinition(
            name="math",
            stages=(
                StageDefinition(name="double", capability="cap.double"),
                StageDefinition(name="increment", capability="cap.increment"),
            ),
        )
    )

    result = engine.run("math", initial_input=10)

    assert result.succeeded
    assert result.output == 21
    assert [r.stage_name for r in result.stage_records] == ["double", "increment"]
    assert all(r.attempts == 1 for r in result.stage_records)


def test_retry_requested_is_retried_up_to_max_attempts_then_succeeds() -> None:
    container = Container()
    attempts = {"n": 0}

    def flaky(data, ctx):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return None, StageOutcome.RETRY_REQUESTED
        return "done", StageOutcome.SUCCESS

    container.register("cap.flaky", lambda: flaky)
    engine = PipelineEngine(container)
    engine.register(
        PipelineDefinition(name="p", stages=(StageDefinition(name="flaky", capability="cap.flaky", max_attempts=5),))
    )

    result = engine.run("p")

    assert result.succeeded
    assert result.output == "done"
    assert result.stage_records[0].attempts == 3


def test_retries_exhausted_marks_the_run_failed() -> None:
    container = Container()
    container.register("cap.always_retry", lambda: (lambda d, ctx: (None, StageOutcome.RETRY_REQUESTED)))
    engine = PipelineEngine(container)
    engine.register(
        PipelineDefinition(
            name="p", stages=(StageDefinition(name="s", capability="cap.always_retry", max_attempts=3),)
        )
    )

    result = engine.run("p")

    assert not result.succeeded
    assert result.state is PipelineRunState.ROLLED_BACK
    assert result.stage_records[0].attempts == 3


def test_a_raising_stage_is_treated_as_failure_not_propagated() -> None:
    container = Container()

    def raises(data, ctx):
        raise ValueError("boom")

    container.register("cap.raises", lambda: raises)
    engine = PipelineEngine(container)
    engine.register(PipelineDefinition(name="p", stages=(StageDefinition(name="s", capability="cap.raises"),)))

    result = engine.run("p")  # must not raise

    assert not result.succeeded
    assert result.stage_records[0].outcome is StageOutcome.FAILURE
    assert "boom" in (result.stage_records[0].error or "")


def test_rollback_runs_in_reverse_order_for_completed_stages_only() -> None:
    container = Container()
    rollback_log: list[str] = []

    container.register("cap.ok1", _success_stage(lambda d: "out1"))
    container.register("rollback.ok1", lambda: (lambda output, ctx: rollback_log.append(f"rb:{output}")))
    container.register("cap.ok2", _success_stage(lambda d: "out2"))
    container.register("rollback.ok2", lambda: (lambda output, ctx: rollback_log.append(f"rb:{output}")))
    container.register("cap.fail", lambda: (lambda d, ctx: (None, StageOutcome.FAILURE)))

    engine = PipelineEngine(container)
    engine.register(
        PipelineDefinition(
            name="p",
            stages=(
                StageDefinition(name="ok1", capability="cap.ok1", rollback_capability="rollback.ok1"),
                StageDefinition(name="ok2", capability="cap.ok2", rollback_capability="rollback.ok2"),
                StageDefinition(name="fail", capability="cap.fail"),
            ),
        )
    )

    result = engine.run("p")

    assert not result.succeeded
    assert rollback_log == ["rb:out2", "rb:out1"]  # reverse order
    by_name = {r.stage_name: r for r in result.stage_records}
    assert by_name["ok1"].rolled_back
    assert by_name["ok2"].rolled_back
    assert not by_name["fail"].rolled_back


def test_pipeline_run_publishes_state_changed_events() -> None:
    container = Container()
    container.register("cap.a", _success_stage(lambda d: d))
    bus = EventBus()
    events: list[str] = []
    bus.subscribe("PipelineRunStateChanged", lambda e: events.append(e.payload["state"]))

    engine = PipelineEngine(container, event_bus=bus)
    engine.register(PipelineDefinition(name="p", stages=(StageDefinition(name="a", capability="cap.a"),)))
    engine.run("p")

    deadline = time.monotonic() + 2.0
    while len(events) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    bus.shutdown()

    assert events == ["running", "completed"]


def test_registered_pipelines_and_get_definition() -> None:
    container = Container()
    container.register("cap.a", _success_stage(lambda d: d))
    engine = PipelineEngine(container)
    assert engine.registered_pipelines() == ()

    definition = PipelineDefinition(name="p", stages=(StageDefinition(name="a", capability="cap.a"),))
    engine.register(definition)

    assert engine.registered_pipelines() == ("p",)
    assert engine.get_definition("p") is definition
    assert engine.get_definition("missing") is None
