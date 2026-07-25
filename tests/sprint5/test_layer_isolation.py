"""Sprint 5, Phase 7 — Layer Isolation.

Two specific claims about `ExecutionEngine`, each verified two ways where
applicable: a precise AST check (so a docstring merely *mentioning* a name
can never produce a false pass — only a real `ast.Name`/`ast.Attribute`
node counts), and a runtime check using a forbidden double
(`tests/sprint5/conftest.py`) — proving, not merely asserting, that the
call path in question never actually touches what it must not.
"""

from __future__ import annotations

import ast
from pathlib import Path

from integration.registry import ConnectorRegistry
from planning.contract import Plan, PlanStep, RuntimeContextInfo

from execution.cancellation import CancellationToken
from execution.confirmation import ConfirmationProvider, DenyAllConfirmationProvider
from execution.connector_invoker import RegistryConnectorInvoker
from execution.context import ExecutionContext
from execution.engine import ExecutionEngine
from execution.lifecycle import ExecutionRunState
from execution.retry import RetryPolicy
from execution.rollback import RollbackStrategy
from tests.sprint5.conftest import ForbiddenConfirmationProvider, ForbiddenRollbackStrategy

EXECUTION_DIR = Path(__file__).resolve().parents[2] / "execution"


def _names_referenced(py_file: Path) -> set[str]:
    """Every bare name and attribute-access name referenced anywhere in
    `py_file` — immune to docstring/comment false positives, since string
    literals never parse as `ast.Name`/`ast.Attribute` nodes.
    """

    tree = ast.parse((EXECUTION_DIR / py_file).read_text(encoding="utf-8"), filename=py_file.name)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _one_step_plan(step: PlanStep) -> Plan:
    return Plan(
        plan_id="P-1", goal_id="G-1", steps=(step,), created_at="2026-01-01T00:00:00Z", strategy_name="stub"
    )


def _context(
    *,
    confirmation_provider: ConfirmationProvider,
    rollback_strategy: RollbackStrategy,
    registry: ConnectorRegistry,
) -> ExecutionContext:
    return ExecutionContext(
        connector_invoker=RegistryConnectorInvoker(registry),
        confirmation_provider=confirmation_provider,
        rollback_strategy=rollback_strategy,
        runtime_context=RuntimeContextInfo(environment="Development", requested_by="test-suite"),
        correlation_id="corr-1",
        cancellation_token=CancellationToken(),
    )


# -- 1. ExecutionEngine never references ConnectorRegistry directly -----------------------


def test_engine_source_never_references_connector_registry() -> None:
    assert "ConnectorRegistry" not in _names_referenced(Path("engine.py"))


def _references_connector_registry(py_file: Path) -> bool:
    """A real AST reference to `ConnectorRegistry` — a `Name`/import
    `alias` node, never a docstring merely mentioning the word (e.g.
    `execution/__init__.py`'s own module docstring, which discusses
    `ConnectorRegistry` in prose without importing it).
    """

    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=py_file.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "ConnectorRegistry":
            return True
        if isinstance(node, ast.alias) and (node.asname or node.name) == "ConnectorRegistry":
            return True
    return False


def test_connector_registry_is_only_imported_by_the_modules_that_legitimately_need_it() -> None:
    # retry.py resolves classification (§17); connector_invoker.py wraps
    # the registry itself (§9.3) -- ExecutionEngine touches neither
    # directly, only through the narrow ConnectorInvoker/RetryPolicy seams
    # (test_engine_source_never_references_connector_registry, above,
    # still proves this). module.py (Sprint 6 Architecture Package §6.2,
    # §7.2) is a third, legitimate consumer, added after Sprint 5's own
    # release: ADR-0014 requires ExecutionModule to resolve
    # integration.connector_registry itself, to construct the RetryPolicy
    # it hands to ExecutionEngine -- the identical reasoning already
    # justifying retry.py's own need, one layer up.
    importers = {
        py_file.name
        for py_file in sorted(EXECUTION_DIR.glob("*.py"))
        if _references_connector_registry(py_file)
    }
    assert importers == {"retry.py", "connector_invoker.py", "module.py"}


# -- 2. A step not requiring confirmation never consults ConfirmationProvider -------------
# -- and a run that never reaches FAILED never triggers a rollback pass -------------------


def test_engine_runtime_never_touches_a_forbidden_confirmation_provider_or_rollback_strategy(
    real_registry: ConnectorRegistry,
) -> None:
    engine = ExecutionEngine(RetryPolicy(real_registry))
    context = _context(
        confirmation_provider=ForbiddenConfirmationProvider(),
        rollback_strategy=ForbiddenRollbackStrategy(),
        registry=real_registry,
    )
    step = PlanStep(
        step_id="S-1", capability="filesystem.exists", requires_confirmation=False, parameters={"path": "x"}
    )

    result = engine.execute(_one_step_plan(step), context)  # must not raise

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.rollback_attempted is False


def test_a_denied_confirmation_never_reaches_forbidden_rollback_strategy(
    real_registry: ConnectorRegistry,
) -> None:
    # A SKIPPED (denied-confirmation) step never fails the run, so the run
    # still never reaches FAILED here either -- rollback stays untouched.
    engine = ExecutionEngine(RetryPolicy(real_registry))
    context = _context(
        confirmation_provider=DenyAllConfirmationProvider(),
        rollback_strategy=ForbiddenRollbackStrategy(),
        registry=real_registry,
    )
    step = PlanStep(
        step_id="S-1",
        capability="filesystem.write_text",
        requires_confirmation=True,
        parameters={"path": "x", "content": "y"},
    )

    result = engine.execute(_one_step_plan(step), context)  # must not raise

    assert result.final_state is ExecutionRunState.COMPLETED
    assert result.rollback_attempted is False
