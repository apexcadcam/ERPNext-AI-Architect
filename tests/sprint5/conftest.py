"""Shared fixtures for Sprint 5's final validation suite.

Self-contained, mirroring `tests/sprint4/conftest.py`'s own discipline:
this directory does not import fixtures or test doubles from
`tests/execution/` (a sibling, not an ancestor, so pytest would not
cascade them here anyway), to avoid cross-test-file coupling between what
each phase's own test suite independently proves.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from integration.contract import ConnectorResponse
from integration.registry import ConnectorRegistry, DiscoveredConnector
from knowledge.graph import InMemoryGraphStore
from planning.contract import CapabilityDescriptor, Goal, PlanStep, RuntimeContextInfo
from planning.context import PlanningContext

from execution.confirmation import ConfirmationProvider
from execution.contract import ExecutionRun, RollbackOutcome, StepExecutionRecord
from execution.rollback import RollbackStrategy

if TYPE_CHECKING:
    from execution.context import ExecutionContext

REPO_ROOT = Path(__file__).resolve().parents[2]
CONNECTORS_DIR = REPO_ROOT / "integration" / "connectors"
EXECUTION_DIR = REPO_ROOT / "execution"


class ConnectorAccessForbidden(AssertionError):
    """Raised by `ForbiddenConnectorInvoker` if anything calls one of its
    methods."""


class ForbiddenConnectorInvoker:
    """A `ConnectorInvoker`-shaped double where every method raises — used
    to *prove*, not merely assert, that a given call path never invokes a
    connector.
    """

    def is_available(self, capability: str) -> bool:
        raise ConnectorAccessForbidden("is_available")

    def invoke(
        self, capability: str, parameters: dict[str, Any], *, correlation_id: str, requested_by: str
    ) -> ConnectorResponse:
        raise ConnectorAccessForbidden("invoke")


class ForbiddenConfirmationProvider(ConfirmationProvider):
    """A `ConfirmationProvider` double whose `confirm()` always raises —
    used to prove a step that does not require confirmation never
    consults it, at the full `ExecutionEngine` level.
    """

    def confirm(self, step: PlanStep, run: ExecutionRun) -> bool:
        raise AssertionError("confirm() must never be called for a step that does not require it")


class ForbiddenRollbackStrategy(RollbackStrategy):
    """A `RollbackStrategy` whose `rollback()` always raises — used to
    prove a run that never reaches `FAILED` never triggers a rollback
    pass. A real subclass, not merely a structurally-shaped double,
    since `ExecutionContext.rollback_strategy` is validated by `isinstance`
    (§9.5 is a nominal `ABC`, unlike `ConnectorInvoker`'s structural
    `Protocol`).
    """

    def rollback(self, record: StepExecutionRecord, context: ExecutionContext) -> RollbackOutcome:
        raise AssertionError("rollback() must never be called for a run that did not end FAILED")


@pytest.fixture
def real_registry(tmp_path: Path) -> ConnectorRegistry:
    """The real Filesystem connector (Sprint 3/5 Phase 1), rooted at a
    fresh `tmp_path`, discovered through `ConnectorRegistry`'s own public
    API — no private internals touched, mirroring
    `tests/execution/test_connector_invoker.py`'s own pattern.
    """

    registry = ConnectorRegistry()
    discovered = registry.discover([CONNECTORS_DIR])
    patched = [
        DiscoveredConnector(
            manifest=connector.manifest.model_copy(update={"endpoint_reference": str(tmp_path)}),
            connector_dir=connector.connector_dir,
        )
        for connector in discovered
    ]
    registry.register_all(patched)
    registry.validate()
    return registry


@pytest.fixture
def goal() -> Goal:
    return Goal(
        goal_id="G-1",
        intent="read then write a file",
        desired_capabilities=("filesystem.read_text", "filesystem.write_text"),
    )


@pytest.fixture
def planning_context() -> PlanningContext:
    return PlanningContext(
        graph=InMemoryGraphStore(),
        available_capabilities=(
            CapabilityDescriptor(
                capability="filesystem.read_text", kind="read", idempotent=True, requires_confirmation=False
            ),
            CapabilityDescriptor(
                capability="filesystem.write_text", kind="write", idempotent=False, requires_confirmation=True
            ),
        ),
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
    )
