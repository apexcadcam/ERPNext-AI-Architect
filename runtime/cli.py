"""The `architect` CLI.

Implements docs/runtime/CLI_ARCHITECTURE.md: every command resolves to a
Runtime lifecycle operation, none bypasses validation, and structured
output (`--json`) always mirrors what a human-readable render shows —
never a second, divergent code path (§4).

Sprint 1 provided the five original commands: `--help` (automatic),
`doctor`, `plugins list`, `runtime info`, `config validate`. Every one of
those constructs its own ephemeral Runtime for the duration of the
invocation and tears it down before exiting — Sprint 1 had no
long-running daemon/IPC layer, and none exists here now either.

**Sprint 14, Phase 2 (ADR-005) adds one more: `run-goal`.** Per ADR-005,
this is a disclosed, narrow, additive exception to the Runtime package's
own freeze — every other command above is untouched. `run-goal` is a thin
adapter only: it parses an input file into the existing
`RawRequirement`/`Goal`/`CapabilityDescriptor` contracts (via their own
`model_validate`, no new validation logic), calls the existing
`composition_root.run_goal_end_to_end` (Sprint 13) exactly once, and
renders the resulting `GoalRunResult`. It never constructs a
`PlanningEngine`/`ExecutionEngine`/`GoalOrchestrator`/`PluginRegistry`/
`Container` itself, and never imports `intelligence.pipeline` or
`intelligence.bridge` — every one of those already lives inside
`composition_root` itself.
"""

from __future__ import annotations

import json as json_module
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError

from analysis.requirements.raw import RawRequirement
from planning.contract import CapabilityDescriptor, Goal

from composition_root import run_goal_end_to_end
from orchestration.contract import GoalRunResult

from runtime.boot import Runtime
from runtime.errors import RuntimeError_

app = typer.Typer(
    name="architect",
    help="ERPNext AI Architect — Core Runtime Platform CLI.",
    no_args_is_help=True,
)
plugins_app = typer.Typer(help="Plugin Registry operations.", no_args_is_help=True)
runtime_app = typer.Typer(help="Runtime process operations.", no_args_is_help=True)
config_app = typer.Typer(help="Configuration System operations.", no_args_is_help=True)
app.add_typer(plugins_app, name="plugins")
app.add_typer(runtime_app, name="runtime")
app.add_typer(config_app, name="config")


#: Exit codes — CLI_ARCHITECTURE.md §5, deliberately small in Sprint 1
#: (no ERROR_HANDLING.md-style category mapping exists at this layer yet;
#: see the implementation summary's Sprint 2 backlog).
EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_INTERNAL_ERROR = 2

ConfigDirOption = Annotated[
    Path,
    typer.Option("--config-dir", help="Directory holding global.yaml / environments / modules / pipelines / connectors."),
]
PluginPathOption = Annotated[
    list[Path] | None,
    typer.Option("--plugin-path", help="A directory to search for plugin manifests. Repeatable."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON instead of a human-readable render.")]
EnvironmentOption = Annotated[
    str | None, typer.Option("--environment", help="Overrides the environment layer (default: development).")
]


def _build_runtime(config_dir: Path, plugin_paths: list[Path] | None, environment: str | None) -> Runtime:
    return Runtime(
        config_dir=config_dir,
        plugin_search_paths=plugin_paths or [],
        environment=environment,
    )


def _emit(data: Mapping[str, object], *, as_json: bool, render: str) -> None:
    if as_json:
        typer.echo(json_module.dumps(data, indent=2, default=str))
    else:
        typer.echo(render)


@app.command()
def doctor(
    config_dir: ConfigDirOption = Path("config"),
    plugin_path: PluginPathOption = None,
    environment: EnvironmentOption = None,
    json: JsonOption = False,
) -> None:
    """Boot the Runtime, run every module's health check, and report.

    Exit code 0 if the Runtime booted and every started module is healthy
    (vacuously true with zero modules — CLI_ARCHITECTURE.md never treats an
    empty, valid state as a failure). Non-zero otherwise.
    """

    runtime = _build_runtime(config_dir, plugin_path, environment)
    try:
        info = runtime.boot()
    except RuntimeError_ as exc:
        _emit(
            {"ok": False, "stage": "boot", "error": str(exc)},
            as_json=json,
            render=f"Runtime failed to boot: {exc}",
        )
        raise typer.Exit(EXIT_VALIDATION_FAILED) from exc

    try:
        healthy = runtime.all_healthy()
        result = {
            "ok": healthy,
            "runtime_state": info.state.value,
            "environment": info.environment,
            "discovered_modules": info.discovered_module_count,
            "enabled_modules": info.enabled_module_count,
            "started_modules": info.started_module_count,
            "module_health": {
                module_id: {"healthy": health.healthy, "detail": health.detail}
                for module_id, health in info.module_health.items()
            },
        }
        if json:
            _emit(result, as_json=True, render="")
        else:
            lines = [f"Runtime: {info.state.value} (environment={info.environment})"]
            lines.append(
                f"Modules: {info.discovered_module_count} discovered, "
                f"{info.enabled_module_count} enabled, {info.started_module_count} started"
            )
            if not info.module_health:
                lines.append("No modules installed yet — nothing to health-check. This is expected in Sprint 1.")
            for module_id, health in info.module_health.items():
                mark = "OK" if health.healthy else "FAIL"
                lines.append(f"  [{mark}] {module_id}: {health.detail}")
            lines.append("Overall: HEALTHY" if healthy else "Overall: UNHEALTHY")
            _emit({}, as_json=False, render="\n".join(lines))
    finally:
        runtime.shutdown()

    raise typer.Exit(EXIT_OK if healthy else EXIT_VALIDATION_FAILED)


InputFileArgument = Annotated[
    Path,
    typer.Argument(help="YAML (or JSON) file describing the requirement, goal, and available capabilities."),
]
CreatedAtOption = Annotated[
    str | None,
    typer.Option("--created-at", help="Timestamp stamped on the derived Knowledge/Plan (default: now)."),
]
CorrelationIdOption = Annotated[
    str | None, typer.Option("--correlation-id", help="Correlation id for this run (default: a fresh id).")
]


def _goal_state(result: GoalRunResult) -> str:
    if result.planning_failure is not None:
        return "planning_failed"
    if result.execution_result is not None:
        return result.execution_result.final_state.value
    return "unknown"  # pragma: no cover - GoalRunResult's own contract makes this unreachable


def _goal_run_result_payload(result: GoalRunResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "goal_id": result.goal_id,
        "goal_state": _goal_state(result),
        "planning_failure": None,
        "plan": None,
        "execution_result": None,
    }
    if result.planning_failure is not None:
        payload["planning_failure"] = {
            "error_type": result.planning_failure.error_type,
            "detail": result.planning_failure.detail,
        }
    if result.plan is not None:
        payload["plan"] = {
            "plan_id": result.plan.plan_id,
            "strategy_name": result.plan.strategy_name,
            "created_at": result.plan.created_at,
            "steps": [
                {
                    "step_id": step.step_id,
                    "capability": step.capability,
                    "requires_confirmation": step.requires_confirmation,
                    "depends_on": list(step.depends_on),
                    "rationale": step.rationale,
                }
                for step in result.plan.steps
            ],
        }
    if result.execution_result is not None:
        payload["execution_result"] = {
            "execution_run_id": result.execution_result.execution_run_id,
            "final_state": result.execution_result.final_state.value,
            "rollback_attempted": result.execution_result.rollback_attempted,
            "step_records": [
                {
                    "step_id": record.step_id,
                    "state": record.state.value,
                    "attempts": record.attempts,
                    "response_status": record.response.status if record.response is not None else None,
                    "response_diagnostics": (
                        record.response.diagnostics if record.response is not None else None
                    ),
                }
                for record in result.execution_result.step_records
            ],
        }
    return payload


def _render_goal_run_result(result: GoalRunResult) -> str:
    lines = [f"Goal: {result.goal_id}"]
    if result.planning_failure is not None:
        lines.append(
            f"Planning failed: {result.planning_failure.error_type} — {result.planning_failure.detail}"
        )
    if result.plan is not None:
        lines.append(f"Strategy: {result.plan.strategy_name}")
        lines.append(f"Plan: {result.plan.plan_id} ({len(result.plan.steps)} step(s))")
        for step in result.plan.steps:
            confirmation = "yes" if step.requires_confirmation else "no"
            lines.append(f"  [{step.step_id}] {step.capability}  (confirmation required: {confirmation})")
    if result.execution_result is not None:
        lines.append(f"Execution: {result.execution_result.final_state.value.upper()}")
        for record in result.execution_result.step_records:
            detail = record.response.diagnostics if record.response is not None else ""
            suffix = f" — {detail}" if detail else ""
            lines.append(f"  [{record.step_id}] {record.state.value.upper()}{suffix}")
    lines.append(f"Goal state: {_goal_state(result).upper()}")
    return "\n".join(lines)


@app.command("run-goal")
def run_goal(
    input_file: InputFileArgument,
    config_dir: ConfigDirOption = Path("config"),
    plugin_path: PluginPathOption = None,
    created_at: CreatedAtOption = None,
    correlation_id: CorrelationIdOption = None,
    json: JsonOption = False,
) -> None:
    """Parse INPUT_FILE, run it through the real Composition Root
    (`composition_root.run_goal_end_to_end`), and render the resulting
    `GoalRunResult`. A thin adapter only — see `composition_root/root.py`
    for the actual Analysis -> Knowledge -> ... -> Execution sequence this
    command triggers exactly once and does not itself reimplement.

    Exit code 0 only if the goal fully completed (`planning_failure` is
    `None` and execution reached `COMPLETED`); 1 if the goal did not fully
    succeed (a Planning failure, or execution ending `FAILED`/`CANCELLED`)
    or the input/Runtime boot itself failed; 2 for anything unexpected —
    mirroring `doctor`'s own "0 only if truly healthy" exit-code
    discipline, applied to goal outcome instead of module health.
    """

    try:
        raw_text = input_file.read_text(encoding="utf-8")
    except OSError as exc:
        message = f"Could not read input file '{input_file}': {exc}"
        _emit({"ok": False, "error": message}, as_json=json, render=message)
        raise typer.Exit(EXIT_VALIDATION_FAILED) from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        message = f"Input file is not valid YAML: {exc}"
        _emit({"ok": False, "error": message}, as_json=json, render=message)
        raise typer.Exit(EXIT_VALIDATION_FAILED) from exc

    if not isinstance(data, dict) or "requirement" not in data or "goal" not in data:
        message = "Input file must be a mapping with, at minimum, 'requirement' and 'goal' keys."
        _emit({"ok": False, "error": message}, as_json=json, render=message)
        raise typer.Exit(EXIT_VALIDATION_FAILED)

    try:
        requirement = RawRequirement.model_validate(data["requirement"])
        goal = Goal.model_validate(data["goal"])
        available_capabilities = tuple(
            CapabilityDescriptor.model_validate(item) for item in data.get("available_capabilities", [])
        )
    except ValidationError as exc:
        message = f"Input file failed validation:\n{exc}"
        _emit({"ok": False, "error": str(exc)}, as_json=json, render=message)
        raise typer.Exit(EXIT_VALIDATION_FAILED) from exc

    try:
        result = run_goal_end_to_end(
            requirement,
            goal,
            available_capabilities,
            plugin_search_paths=plugin_path or [Path("plugins")],
            config_dir=config_dir,
            created_at=created_at or datetime.now(UTC).isoformat(),
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
    except RuntimeError_ as exc:
        message = f"Runtime failed to boot: {exc}"
        _emit({"ok": False, "stage": "boot", "error": str(exc)}, as_json=json, render=message)
        raise typer.Exit(EXIT_VALIDATION_FAILED) from exc

    if json:
        _emit(_goal_run_result_payload(result), as_json=True, render="")
    else:
        _emit({}, as_json=False, render=_render_goal_run_result(result))

    succeeded = result.planning_failure is None and _goal_state(result) == "completed"
    raise typer.Exit(EXIT_OK if succeeded else EXIT_VALIDATION_FAILED)


@runtime_app.command("info")
def runtime_info(
    config_dir: ConfigDirOption = Path("config"),
    plugin_path: PluginPathOption = None,
    environment: EnvironmentOption = None,
    json: JsonOption = False,
) -> None:
    """Boot the Runtime and report its summary state, then shut down."""

    runtime = _build_runtime(config_dir, plugin_path, environment)
    try:
        info = runtime.boot()
    except RuntimeError_ as exc:
        _emit({"ok": False, "error": str(exc)}, as_json=json, render=f"Runtime failed to boot: {exc}")
        raise typer.Exit(EXIT_VALIDATION_FAILED) from exc

    try:
        result = {
            "state": info.state.value,
            "environment": info.environment,
            "discovered_modules": info.discovered_module_count,
            "enabled_modules": info.enabled_module_count,
            "started_modules": info.started_module_count,
            "registered_pipelines": info.registered_pipeline_count,
            "dependency_order": list(info.dependency_order),
        }
        if json:
            _emit(result, as_json=True, render="")
        else:
            lines = [
                f"State: {info.state.value}",
                f"Environment: {info.environment}",
                f"Modules discovered: {info.discovered_module_count}",
                f"Modules enabled: {info.enabled_module_count}",
                f"Modules started: {info.started_module_count}",
                f"Pipelines registered: {info.registered_pipeline_count}",
                f"Startup order: {', '.join(info.dependency_order) or '(none)'}",
            ]
            _emit({}, as_json=False, render="\n".join(lines))
    finally:
        runtime.shutdown()

    raise typer.Exit(EXIT_OK)


@plugins_app.command("list")
def plugins_list(
    plugin_path: PluginPathOption = None,
    json: JsonOption = False,
) -> None:
    """Discover and list every plugin found on `--plugin-path`, without
    booting the Runtime (no init()/start()/health_check() runs here — this
    command only ever reads manifests).
    """

    from runtime.registry.plugin_registry import PluginRegistry

    registry = PluginRegistry()
    discovered = registry.discover(plugin_path or [])
    registry.register_all(discovered)

    if json:
        _emit(
            {
                "plugins": [
                    {
                        "module_id": p.manifest.module_id,
                        "display_name": p.manifest.display_name,
                        "version": p.manifest.version,
                        "enabled_by_default": p.manifest.enabled_by_default,
                        "capabilities_provided": list(p.manifest.capabilities_provided),
                        "capabilities_required": list(p.manifest.capabilities_required),
                    }
                    for p in discovered
                ]
            },
            as_json=True,
            render="",
        )
        raise typer.Exit(EXIT_OK)

    if not discovered:
        typer.echo("No plugins installed. This is expected in Sprint 1 — the Plugin Registry is ready to discover them.")
        raise typer.Exit(EXIT_OK)

    for plugin in discovered:
        m = plugin.manifest
        typer.echo(f"{m.module_id}  ({m.display_name} v{m.version}, enabled_by_default={m.enabled_by_default})")
        if m.capabilities_provided:
            typer.echo(f"    provides: {', '.join(m.capabilities_provided)}")
        if m.capabilities_required:
            typer.echo(f"    requires: {', '.join(m.capabilities_required)}")

    raise typer.Exit(EXIT_OK)


@config_app.command("validate")
def config_validate(
    config_dir: ConfigDirOption = Path("config"),
    environment: EnvironmentOption = None,
    json: JsonOption = False,
) -> None:
    """Validate the Global and Environment configuration layers, without
    booting the Runtime — CONFIGURATION_SYSTEM.md §4's validation gate, run
    standalone.
    """

    from runtime.config.loader import ConfigLoader

    loader = ConfigLoader(config_dir, environment=environment)
    try:
        issues = loader.validate()
    except Exception as exc:  # unexpected — not a validation-shaped failure
        _emit({"ok": False, "error": str(exc)}, as_json=json, render=f"Unexpected error during validation: {exc}")
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    if json:
        _emit({"ok": not issues, "issues": [str(i) for i in issues]}, as_json=True, render="")
    elif issues:
        typer.echo(f"Configuration INVALID — {len(issues)} issue(s):")
        for issue in issues:
            typer.echo(f"  - {issue}")
    else:
        typer.echo(f"Configuration valid (config_dir={config_dir}, environment={loader.environment}).")

    raise typer.Exit(EXIT_OK if not issues else EXIT_VALIDATION_FAILED)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
