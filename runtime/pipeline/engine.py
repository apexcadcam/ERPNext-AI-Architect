"""The Pipeline Engine: a generic, configurable stage-sequencing executor.

Implements docs/runtime/PIPELINE_ENGINE.md. A Pipeline Definition is data —
an ordered list of named stages, each bound to a module capability the
Engine resolves through the Container (§1). The Engine never has stage
*logic* of its own compiled in; every existing pipeline this project has
already designed (CRAWLER_PIPELINE.md's nine stages, KNOWLEDGE_PIPELINE.md's
four, ...) is meant to register as a PipelineDefinition running unmodified
on this same engine (RUNTIME_ARCHITECTURE.md §4.1) — Sprint 1 implements
only the engine itself, with no such definitions registered yet.
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from runtime.container.di import Container
from runtime.errors import PipelineDefinitionError, StageExecutionError
from runtime.events.bus import Event, EventBus
from runtime.lifecycle import PipelineRunState, new_pipeline_run_lifecycle
from runtime.observability.logging import bind_correlation

logger = logging.getLogger(__name__)


class StageOutcome(enum.Enum):
    """See PIPELINE_ENGINE.md §2."""

    SUCCESS = "success"
    FAILURE = "failure"
    RETRY_REQUESTED = "retry_requested"


@dataclass(frozen=True)
class PipelineContext:
    """Carried into every stage invocation — PIPELINE_ENGINE.md §2's
    `pipeline_context`. Also the value LOGGING_AND_OBSERVABILITY.md §2's
    correlation IDs are bound from for the duration of a run.
    """

    pipeline_run_id: str
    correlation_id: str
    pipeline_name: str
    started_at: datetime


#: A stage capability resolves to a callable of exactly this shape
#: (PIPELINE_ENGINE.md §2's stage execution contract).
StageCallable = Callable[[Any, PipelineContext], tuple[Any, StageOutcome]]
#: A rollback capability resolves to a callable taking the stage's own
#: output and the context — never invoked to delete anything, only to mark
#: what that stage produced as rolled back (PIPELINE_ENGINE.md §6).
RollbackCallable = Callable[[Any, PipelineContext], None]


@dataclass(frozen=True)
class StageDefinition:
    name: str
    capability: str
    max_attempts: int = 1
    backoff_base_seconds: float = 0.0
    rollback_capability: str | None = None


@dataclass(frozen=True)
class PipelineDefinition:
    """PIPELINE_ENGINE.md §1: "a Pipeline Definition is data, not code."""

    name: str
    stages: tuple[StageDefinition, ...]

    def __post_init__(self) -> None:
        if not self.stages:
            raise PipelineDefinitionError(f"pipeline '{self.name}' has no stages")
        names = [s.name for s in self.stages]
        if len(names) != len(set(names)):
            raise PipelineDefinitionError(f"pipeline '{self.name}' has duplicate stage names: {names}")


@dataclass
class StageExecutionRecord:
    stage_name: str
    attempts: int
    outcome: StageOutcome
    duration_seconds: float
    error: str | None = None
    rolled_back: bool = False


@dataclass
class PipelineRunResult:
    pipeline_run_id: str
    pipeline_name: str
    state: PipelineRunState
    stage_records: list[StageExecutionRecord] = field(default_factory=list)
    output: Any = None

    @property
    def succeeded(self) -> bool:
        return self.state is PipelineRunState.COMPLETED


class PipelineEngine:
    """Registers Pipeline Definitions and executes them.

    Sequential execution only in Sprint 1 — PIPELINE_ENGINE.md §8 notes
    parallel/distributed execution is a property of *where* a stage
    invocation physically runs, never of how the Engine sequences and
    tracks it, so nothing here needs to change shape to support that later.
    """

    def __init__(self, container: Container, event_bus: EventBus | None = None) -> None:
        self.container = container
        self.event_bus = event_bus
        self._definitions: dict[str, PipelineDefinition] = {}

    def register(self, definition: PipelineDefinition) -> None:
        if definition.name in self._definitions:
            raise PipelineDefinitionError(f"pipeline '{definition.name}' is already registered")
        self._definitions[definition.name] = definition
        logger.info("registered pipeline", extra={"pipeline_name": definition.name, "stage_count": len(definition.stages)})

    def registered_pipelines(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def get_definition(self, name: str) -> PipelineDefinition | None:
        return self._definitions.get(name)

    def run(
        self,
        name: str,
        initial_input: Any = None,
        *,
        correlation_id: str | None = None,
    ) -> PipelineRunResult:
        definition = self._definitions.get(name)
        if definition is None:
            raise PipelineDefinitionError(f"no pipeline registered with name '{name}'")

        run_id = str(uuid.uuid4())
        correlation_id = correlation_id or run_id
        context = PipelineContext(
            pipeline_run_id=run_id,
            correlation_id=correlation_id,
            pipeline_name=name,
            started_at=datetime.now(UTC),
        )
        run_lifecycle = new_pipeline_run_lifecycle()

        with bind_correlation(correlation_id=correlation_id, pipeline_run_id=run_id):
            logger.info("pipeline run starting", extra={"pipeline_name": name})
            run_lifecycle.transition(PipelineRunState.RUNNING)
            self._emit_run_state_changed(context, run_lifecycle.state)

            data = initial_input
            records: list[StageExecutionRecord] = []
            completed: list[tuple[StageDefinition, Any]] = []

            for stage in definition.stages:
                record, data, outcome = self._execute_stage(stage, data, context)
                records.append(record)

                if outcome is not StageOutcome.SUCCESS:
                    self._rollback(completed, context, records)
                    run_lifecycle.transition(PipelineRunState.FAILED)
                    run_lifecycle.transition(PipelineRunState.ROLLING_BACK)
                    run_lifecycle.transition(PipelineRunState.ROLLED_BACK)
                    self._emit_run_state_changed(context, run_lifecycle.state)
                    logger.warning(
                        "pipeline run failed", extra={"pipeline_name": name, "failed_stage": stage.name}
                    )
                    return PipelineRunResult(run_id, name, run_lifecycle.state, records, output=None)

                completed.append((stage, data))

            run_lifecycle.transition(PipelineRunState.COMPLETED)
            self._emit_run_state_changed(context, run_lifecycle.state)
            logger.info("pipeline run completed", extra={"pipeline_name": name})
            return PipelineRunResult(run_id, name, run_lifecycle.state, records, output=data)

    # -- internals -----------------------------------------------------------

    def _execute_stage(
        self, stage: StageDefinition, data: Any, context: PipelineContext
    ) -> tuple[StageExecutionRecord, Any, StageOutcome]:
        stage_fn: StageCallable = self.container.resolve(stage.capability, scope_id=context.pipeline_run_id)

        attempt = 0
        last_error: str | None = None
        while attempt < stage.max_attempts:
            attempt += 1
            start = time.monotonic()
            try:
                output, outcome = stage_fn(data, context)
            except Exception as exc:  # a raising stage is treated as StageOutcome.FAILURE
                duration = time.monotonic() - start
                last_error = str(exc)
                logger.exception(
                    "stage raised", extra={"stage_name": stage.name, "attempt": attempt}
                )
                if attempt < stage.max_attempts:
                    time.sleep(stage.backoff_base_seconds * attempt)
                    continue
                return (
                    StageExecutionRecord(stage.name, attempt, StageOutcome.FAILURE, duration, error=last_error),
                    data,
                    StageOutcome.FAILURE,
                )

            duration = time.monotonic() - start
            if outcome is StageOutcome.SUCCESS:
                return StageExecutionRecord(stage.name, attempt, outcome, duration), output, outcome

            if outcome is StageOutcome.RETRY_REQUESTED and attempt < stage.max_attempts:
                time.sleep(stage.backoff_base_seconds * attempt)
                continue

            return StageExecutionRecord(stage.name, attempt, outcome, duration), data, outcome

        # Unreachable in practice (loop always returns), but keeps type
        # checkers honest about every path producing a result.
        raise StageExecutionError(f"stage '{stage.name}' exhausted retries with no result")

    def _rollback(
        self,
        completed: list[tuple[StageDefinition, Any]],
        context: PipelineContext,
        records: list[StageExecutionRecord],
    ) -> None:
        """PIPELINE_ENGINE.md §6: reverse order, compensating action only —
        never deletes what a prior stage produced.
        """

        records_by_name = {r.stage_name: r for r in records}
        for stage, output in reversed(completed):
            if stage.rollback_capability is None:
                continue
            try:
                rollback_fn: RollbackCallable = self.container.resolve(
                    stage.rollback_capability, scope_id=context.pipeline_run_id
                )
                rollback_fn(output, context)
                if (record := records_by_name.get(stage.name)) is not None:
                    record.rolled_back = True
                logger.info("stage rolled back", extra={"stage_name": stage.name})
            except Exception:
                logger.exception("rollback failed", extra={"stage_name": stage.name})

    def _emit_run_state_changed(self, context: PipelineContext, state: PipelineRunState) -> None:
        if self.event_bus is None:
            return
        self.event_bus.publish(
            Event(
                event_type="PipelineRunStateChanged",
                payload={"pipeline_name": context.pipeline_name, "state": state.value},
                emitted_by="pipeline_engine",
                correlation_id=context.correlation_id,
                pipeline_run_id=context.pipeline_run_id,
            )
        )
