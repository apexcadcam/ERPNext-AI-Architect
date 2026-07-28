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

**The Evidence Platform CLI (Spec v1.1) adds the `evidence` command
group**, following that same adapter discipline exactly, with two rules
this module holds to literally:

1. **No engine import, anywhere in this file.** `evidence` and
   `aggregation` are never imported — not their contracts, not their
   errors, not their enums. Everything this file needs in order to
   validate input and catch failures comes from
   `composition_root.evidence_platform` as plain data:
   `CANONICAL_REPOSITORY_NAMES` (strings) and `EVIDENCE_PLATFORM_ERRORS`
   (exception classes). Spec v1.1 §2 rejected the alternative — a CLI that
   imports two leaf capabilities and grows engine knowledge.
2. **The import is lazy, inside the command.** At module scope this file
   imports `composition_root` for `run_goal`; if the Evidence Platform
   functions were pulled in there, every invocation — `architect doctor`
   included — would load both engines. They are imported inside the
   command body instead, the same way `plugins list` imports
   `PluginRegistry` and `config validate` imports `ConfigLoader`.

Every Evidence Platform command emits a `runtime.output.CommandOutput` and
renders it through the one shared renderer, so `--json` and the human
render cannot diverge (§6).
"""

from __future__ import annotations

import json as json_module
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NoReturn

import typer
import yaml
from pydantic import ValidationError

from analysis.requirements.raw import RawRequirement
from planning.contract import CapabilityDescriptor, Goal

from composition_root import run_goal_end_to_end
from orchestration.contract import GoalRunResult

from runtime.boot import Runtime
from runtime.errors import RuntimeError_
from runtime.output import CommandOutput, emit_command_output

app = typer.Typer(
    name="architect",
    help="ERPNext AI Architect — Core Runtime Platform CLI.",
    no_args_is_help=True,
)
plugins_app = typer.Typer(help="Plugin Registry operations.", no_args_is_help=True)
runtime_app = typer.Typer(help="Runtime process operations.", no_args_is_help=True)
config_app = typer.Typer(help="Configuration System operations.", no_args_is_help=True)
evidence_app = typer.Typer(help="Evidence Platform — extraction operations.", no_args_is_help=True)
patterns_app = typer.Typer(help="Evidence Platform — pattern operations.", no_args_is_help=True)
app.add_typer(plugins_app, name="plugins")
app.add_typer(runtime_app, name="runtime")
app.add_typer(config_app, name="config")
app.add_typer(evidence_app, name="evidence")
app.add_typer(patterns_app, name="patterns")


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


#: Where a canonical repository is expected to be checked out. Overridable
#: per invocation with `--source-root`; a default, never an assumption the
#: command depends on.
DEFAULT_APPS_ROOT = Path("/home/gaber/frappe-bench/apps")

#: Matches the directory the committed corpus already lives in, so a
#: re-extraction lands beside its predecessor and `git diff` shows the
#: change (the reason persistence sorts keys in the first place).
DEFAULT_EVIDENCE_DIR = Path("evidence-data")

#: Extraction limits. `frappe`'s own tree measured 46,296 files examined
#: during Sprint 20's production validation, so a 200,000-file ceiling
#: clears the largest real target with room to spare while still being a
#: real bound; the same run completed in well under a minute, so 900s is
#: generous rather than tight. Both are `--` overridable, and hitting the
#: file ceiling surfaces as a WARNING plus `truncated`, never silently.
DEFAULT_MAX_FILES = 200_000
DEFAULT_TIMEOUT_SECONDS = 900.0

RepositoryArgument = Annotated[str, typer.Argument(help="Canonical repository name: frappe or erpnext.")]
ExtractVersionOption = Annotated[
    str,
    typer.Option("--version", help="Repository version stamped on the Evidence (required: never auto-detected)."),
]
ExtractCommitOption = Annotated[
    str,
    typer.Option("--commit", help="Repository commit stamped on the Evidence (required: never auto-detected)."),
]
AggregateVersionOption = Annotated[
    str,
    typer.Option("--version", help="Which persisted Evidence artifact to aggregate, by version."),
]
SourceRootOption = Annotated[
    Path | None,
    typer.Option("--source-root", help=f"Repository checkout to read (default: {DEFAULT_APPS_ROOT}/<repository>)."),
]
OutputDirOption = Annotated[
    Path, typer.Option("--output-dir", help="Directory the Evidence artifacts are written to.")
]
MaxFilesOption = Annotated[int, typer.Option("--max-files", help="Ceiling on files walked before truncating.")]
TimeoutOption = Annotated[float, typer.Option("--timeout-seconds", help="Wall-clock ceiling for the walk.")]


def _validation_message(exc: ValidationError) -> str:
    """Flatten a pydantic `ValidationError` to one readable line.

    Needed because the Evidence contract enforces some rules deep inside
    the artifact rather than at the request boundary — `Source.commit`'s
    `^[0-9a-f]{7,40}$` pattern is checked while building an `Evidence`
    record, not when `EvidenceExtractionRequest` is constructed. Found by
    running the command rather than by reading the code: without this,
    `--commit abc123` raised a full pydantic traceback from inside the
    collector, which §7 forbids.
    """

    details = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
    return f"Invalid input: {details}"


def _fail(message: str, *, as_json: bool) -> NoReturn:
    """Emit a failing `CommandOutput` and exit.

    The failure path renders the *same* six sections as the success path
    (Spec v1.1 §6) — `ERRORS` populated, everything else empty — so a
    consumer parses both identically instead of branching on shape.
    """

    output = CommandOutput(errors=(message,), exit_code=EXIT_VALIDATION_FAILED)
    emit_command_output(output, as_json=as_json)
    raise typer.Exit(output.exit_code)


@evidence_app.command("extract")
def evidence_extract(
    repository: RepositoryArgument,
    version: ExtractVersionOption,
    commit: ExtractCommitOption,
    source_root: SourceRootOption = None,
    output_dir: OutputDirOption = DEFAULT_EVIDENCE_DIR,
    max_files: MaxFilesOption = DEFAULT_MAX_FILES,
    timeout_seconds: TimeoutOption = DEFAULT_TIMEOUT_SECONDS,
    correlation_id: CorrelationIdOption = None,
    json: JsonOption = False,
) -> None:
    """Run Evidence Extraction against a canonical repository and persist
    the result (Evidence Platform CLI Spec v1.1 §3.1).

    A thin adapter, exactly like `run-goal`: it resolves paths, calls
    `composition_root.evidence_platform.extract_repository_evidence` once,
    and renders the returned `EvidenceSet` as a `CommandOutput`. It
    constructs no request object, imports no engine, and performs no
    counting of its own — every number below is read off the
    `EvidenceStatistics` the engine itself produced.

    `--version` and `--commit` are **required**. The Evidence Extraction
    specification §2 makes provenance a caller-supplied input that is
    never auto-detected, so that a stored `EvidenceSet` always says which
    revision it actually describes. Inferring them from a previous run's
    metadata would let a fresh extraction inherit a stale label silently —
    the one failure mode this platform exists to prevent.
    """

    from composition_root.evidence_platform import (
        CANONICAL_REPOSITORY_NAMES,
        EVIDENCE_PLATFORM_ERRORS,
        extract_repository_evidence,
    )

    if repository not in CANONICAL_REPOSITORY_NAMES:
        _fail(
            f"Unknown repository '{repository}'. Supported: {', '.join(CANONICAL_REPOSITORY_NAMES)}.",
            as_json=json,
        )

    resolved_root = source_root if source_root is not None else DEFAULT_APPS_ROOT / repository
    evidence_path = output_dir / f"{repository}-{version}.evidence.jsonl"
    meta_path = output_dir / f"{repository}-{version}.meta.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        evidence_set = extract_repository_evidence(
            repository=repository,
            source_root=str(resolved_root),
            version=version,
            commit=commit,
            correlation_id=correlation_id or str(uuid.uuid4()),
            requested_by="cli",
            max_files=max_files,
            timeout_seconds=timeout_seconds,
            evidence_path=evidence_path,
            meta_path=meta_path,
        )
    except EVIDENCE_PLATFORM_ERRORS as exc:
        _fail(str(exc), as_json=json)
    except ValidationError as exc:
        _fail(_validation_message(exc), as_json=json)

    statistics = evidence_set.statistics
    warnings = tuple(f"could not parse {error.relative_path}: {error.reason}" for error in evidence_set.errors)
    if evidence_set.truncated:
        warnings = (
            f"the {max_files}-file ceiling was reached; this Evidence describes part of the tree only",
            *warnings,
        )

    output = CommandOutput(
        summary=(
            ("repository", evidence_set.repository.value),
            ("version", evidence_set.version),
            ("commit", evidence_set.commit),
            ("source root", str(resolved_root)),
            ("files examined", str(statistics.files_examined)),
            ("files skipped", str(statistics.files_skipped)),
            ("files failed", str(statistics.files_failed)),
            ("evidence extracted", str(statistics.evidence_extracted)),
        ),
        artifacts_written=(str(evidence_path), str(meta_path)),
        warnings=warnings,
        exit_code=EXIT_OK,
    )
    emit_command_output(output, as_json=json)
    raise typer.Exit(output.exit_code)


#: Where `PatternSet` artifacts are written, matching the directory the
#: committed corpus already occupies.
DEFAULT_PATTERN_DIR = Path("pattern-data")

EvidenceDirOption = Annotated[
    Path, typer.Option("--evidence-dir", help="Directory holding the persisted Evidence artifacts.")
]
PatternDirOption = Annotated[
    Path, typer.Option("--output-dir", help="Directory the Pattern artifacts are written to.")
]
PatternInputDirOption = Annotated[
    Path, typer.Option("--pattern-dir", help="Directory holding the persisted Pattern artifacts.")
]
MinOccurrencesOption = Annotated[
    int | None,
    typer.Option(
        "--min-occurrences",
        help="Occurrence floor below which a subject is recorded but not promoted to a Pattern "
        "(default: the registered MIN_OCCURRENCES_THRESHOLD).",
    ),
]

#: How a `SkippedAggregation` is rendered into the `SKIPPED` section.
#:
#: One template, used by both `patterns aggregate` and `patterns report`,
#: so the two cannot describe the same gap differently. `{reason}` is
#: substituted whole and never truncated: that text is the platform's own
#: account of a limitation it can see but cannot yet measure, and
#: shortening it for terminal tidiness would demote a disclosed gap back
#: to a footnote.
SKIPPED_AGGREGATION_TEMPLATE = (
    "{category} [{status}] — {records} Evidence record(s) present, not aggregated: {reason}"
)


@patterns_app.command("aggregate")
def patterns_aggregate(
    repository: RepositoryArgument,
    version: AggregateVersionOption,
    evidence_dir: EvidenceDirOption = DEFAULT_EVIDENCE_DIR,
    output_dir: PatternDirOption = DEFAULT_PATTERN_DIR,
    min_occurrences: MinOccurrencesOption = None,
    correlation_id: CorrelationIdOption = None,
    json: JsonOption = False,
) -> None:
    """Aggregate a persisted `EvidenceSet` into a `PatternSet` and persist
    it (Evidence Platform CLI Spec v1.1 §3.2).

    Reads the Evidence artifact identified by `<repository>` and
    `--version`; never re-runs extraction and never touches a source tree.

    **Every number printed comes from the engine.** The `SUMMARY` rows are
    `AggregationStatistics` fields verbatim — nothing here counts,
    filters, or derives anything of its own.

    **Every `SkippedAggregation` is printed with its `reason` in full**,
    unedited and untruncated. That reason is the platform's own account of
    a gap it can see but cannot yet measure (the controller-lifecycle-hook
    denominator, today); shortening it for terminal tidiness would turn a
    disclosed limitation back into a footnote.
    """

    from composition_root.evidence_platform import (
        CANONICAL_REPOSITORY_NAMES,
        DEFAULT_MIN_OCCURRENCES,
        EVIDENCE_PLATFORM_ERRORS,
        aggregate_repository_patterns,
    )

    if repository not in CANONICAL_REPOSITORY_NAMES:
        _fail(
            f"Unknown repository '{repository}'. Supported: {', '.join(CANONICAL_REPOSITORY_NAMES)}.",
            as_json=json,
        )

    evidence_path = evidence_dir / f"{repository}-{version}.evidence.jsonl"
    meta_path = evidence_dir / f"{repository}-{version}.meta.json"
    if not evidence_path.is_file():
        _fail(f"No Evidence artifact at '{evidence_path}'. Run `architect evidence extract` first.", as_json=json)

    patterns_path = output_dir / f"{repository}-{version}.patterns.jsonl"
    pattern_meta_path = output_dir / f"{repository}-{version}.meta.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        pattern_set = aggregate_repository_patterns(
            evidence_path=evidence_path,
            meta_path=meta_path,
            patterns_path=patterns_path,
            pattern_meta_path=pattern_meta_path,
            min_occurrences=min_occurrences if min_occurrences is not None else DEFAULT_MIN_OCCURRENCES,
            correlation_id=correlation_id or str(uuid.uuid4()),
            requested_by="cli",
        )
    except EVIDENCE_PLATFORM_ERRORS as exc:
        _fail(str(exc), as_json=json)
    except ValidationError as exc:
        _fail(_validation_message(exc), as_json=json)

    statistics = pattern_set.statistics
    output = CommandOutput(
        summary=(
            ("repository", pattern_set.repository.value),
            ("version", pattern_set.version),
            ("evidence records consumed", str(statistics.evidence_records_consumed)),
            ("categories present", str(statistics.categories_present)),
            ("categories aggregated", str(statistics.categories_aggregated)),
            ("categories skipped", str(statistics.categories_skipped)),
            ("patterns produced", str(statistics.patterns_produced)),
            ("subjects below threshold", str(statistics.subjects_below_threshold)),
        ),
        artifacts_written=(str(patterns_path), str(pattern_meta_path)),
        skipped=tuple(
            SKIPPED_AGGREGATION_TEMPLATE.format(
                category=skipped.evidence_category.value,
                status=skipped.status.value,
                records=skipped.evidence_records_present,
                reason=skipped.reason,
            )
            for skipped in pattern_set.skipped_aggregations
        ),
        exit_code=EXIT_OK,
    )
    emit_command_output(output, as_json=json)
    raise typer.Exit(output.exit_code)


@patterns_app.command("report")
def patterns_report(
    repository: RepositoryArgument,
    version: AggregateVersionOption,
    pattern_dir: PatternInputDirOption = DEFAULT_PATTERN_DIR,
    json: JsonOption = False,
) -> None:
    """Render an already-persisted `PatternSet` (Evidence Platform CLI
    Spec v1.1 §3.3). **Read-only: runs no engine and writes nothing.**

    Renders exactly the four groups §3.3 names, in order: provenance, the
    measured Patterns, the subjects observed below threshold, and the
    skipped aggregations — plus each category's `population_description`,
    stated once, because a share means nothing without its denominator
    named. Nothing else is added: no derived totals, no rankings, no
    commentary.

    **This command performs no arithmetic.** Every number below is a field
    read off the persisted artifact and converted to a string. In
    particular `support` is *formatted*, never recomputed: the CLI does
    not divide `occurrences` by `population`, because a second computation
    of a stored quantity is a second source of truth, and the two would
    eventually disagree. It is printed as the ratio the engine stored,
    because `aggregation.contract.Pattern` deliberately named the field
    `support` — a share, not a percentage — and rescaling it here would be
    the CLI restating the engine's vocabulary in its own terms.

    **Why Patterns and below-threshold subjects appear under `SUMMARY`.**
    §6's six sections are fixed, and `SUMMARY` is the one that carries
    ordered label/value data. Each row is prefixed (`pattern:` /
    `below threshold:`) so the three groups stay distinguishable, and each
    label carries its `evidence_category`, which is what makes the labels
    unique: the engine keys a Pattern by (category, subject), so two
    categories may legitimately share a subject name.

    `ARTIFACTS WRITTEN` is empty for this command, and that is the honest
    report of a read-only operation rather than a missing section.
    """

    from composition_root.evidence_platform import (
        CANONICAL_REPOSITORY_NAMES,
        EVIDENCE_PLATFORM_ERRORS,
        read_repository_patterns,
    )

    if repository not in CANONICAL_REPOSITORY_NAMES:
        _fail(
            f"Unknown repository '{repository}'. Supported: {', '.join(CANONICAL_REPOSITORY_NAMES)}.",
            as_json=json,
        )

    patterns_path = pattern_dir / f"{repository}-{version}.patterns.jsonl"
    pattern_meta_path = pattern_dir / f"{repository}-{version}.meta.json"
    if not patterns_path.is_file():
        _fail(
            f"No Pattern artifact at '{patterns_path}'. Run `architect patterns aggregate` first.",
            as_json=json,
        )

    try:
        pattern_set = read_repository_patterns(
            patterns_path=patterns_path,
            pattern_meta_path=pattern_meta_path,
        )
    except EVIDENCE_PLATFORM_ERRORS as exc:
        # One `except` where `extract` and `aggregate` have two. Those
        # build a pydantic request object, so a `ValidationError` can
        # escape them; this command builds nothing, and
        # `aggregation.persistence.read_pattern_set` converts every
        # `ValueError` -- `ValidationError` included -- into
        # `AggregationError_` before it returns. A second clause here
        # would be unreachable code kept for symmetry's sake.
        _fail(str(exc), as_json=json)

    provenance = (
        ("repository", pattern_set.repository.value),
        ("version", pattern_set.version),
        ("commit", pattern_set.commit),
        ("aggregated at", pattern_set.aggregated_at),
    )
    # One row per category rather than per Pattern: `population_description`
    # is a property of the denominator, identical for every Pattern in a
    # category, so repeating it per row buried the counts in a wall of
    # duplicated text (seen by running the command against the real
    # corpus). Stated once, it also puts the denominator's definition in
    # front of the reader before any share is quoted.
    populations = tuple(
        (f"population: {category}", description)
        for category, description in {
            pattern.evidence_category.value: pattern.population_description
            for pattern in pattern_set.patterns
        }.items()
    )
    measured = tuple(
        (
            f"pattern: {pattern.evidence_category.value} / {pattern.subject}",
            f"{pattern.occurrences}/{pattern.population} (support {pattern.support:.4f})",
        )
        for pattern in pattern_set.patterns
    )
    below_threshold = tuple(
        (
            f"below threshold: {observed.evidence_category.value} / {observed.subject}",
            str(observed.occurrences),
        )
        for observed in pattern_set.observed_below_threshold
    )

    output = CommandOutput(
        summary=provenance + populations + measured + below_threshold,
        skipped=tuple(
            SKIPPED_AGGREGATION_TEMPLATE.format(
                category=skipped.evidence_category.value,
                status=skipped.status.value,
                records=skipped.evidence_records_present,
                reason=skipped.reason,
            )
            for skipped in pattern_set.skipped_aggregations
        ),
        exit_code=EXIT_OK,
    )
    emit_command_output(output, as_json=json)
    raise typer.Exit(output.exit_code)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
