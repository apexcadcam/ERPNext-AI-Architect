"""Tests that the Knowledge Factory Status events named in
docs/studio/STUDIO_EVENT_MODEL.md §2 actually reach a real `EventBus`
during a real end-to-end pipeline run — not merely that the pipeline runs.
See `wired_engine`/`fixture_document` in conftest.py for the shared setup.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from runtime.events.bus import EventBus
from runtime.pipeline.engine import PipelineEngine

from tests.knowledge.conftest import fixture_document


def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0, interval: float = 0.01) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met before timeout")


def _bus_of(engine: PipelineEngine) -> EventBus:
    assert engine.event_bus is not None  # the wired_engine fixture always supplies one
    return engine.event_bus


def test_artifact_created_is_published_during_extraction(wired_engine: PipelineEngine) -> None:
    received: list[dict[str, object]] = []
    _bus_of(wired_engine).subscribe("ArtifactCreated", lambda e: received.append(e.payload))

    wired_engine.run("knowledge.graph_build", initial_input=fixture_document())

    _wait_until(lambda: len(received) == 1)
    assert received[0]["artifact_type"] == "knowledge_api"


def test_validation_completed_is_published_when_an_artifact_is_validated(
    wired_engine: PipelineEngine,
) -> None:
    extracted = wired_engine.run("knowledge.graph_build", initial_input=fixture_document()).output[0]
    received: list[dict[str, object]] = []
    _bus_of(wired_engine).subscribe("ValidationCompleted", lambda e: received.append(e.payload))

    wired_engine.run("knowledge.validation", initial_input=extracted)

    _wait_until(lambda: len(received) == 1)
    assert received[0]["artifact_id"] == extracted.id


def test_pipeline_run_state_changed_is_published_for_both_pipelines(wired_engine: PipelineEngine) -> None:
    received: list[str] = []
    _bus_of(wired_engine).subscribe(
        "PipelineRunStateChanged",
        lambda e: received.append(f"{e.payload['pipeline_name']}:{e.payload['state']}"),
    )

    extracted = wired_engine.run("knowledge.graph_build", initial_input=fixture_document()).output[0]
    wired_engine.run("knowledge.validation", initial_input=extracted)

    _wait_until(lambda: len(received) == 4)  # running+completed, twice
    assert "knowledge.graph_build:completed" in received
    assert "knowledge.validation:completed" in received
