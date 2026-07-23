"""The `architect` CLI.

Implements docs/runtime/CLI_ARCHITECTURE.md: every command resolves to a
Runtime lifecycle operation, none bypasses validation, and structured
output (`--json`) always mirrors what a human-readable render shows —
never a second, divergent code path (§4).

Sprint 1 provides exactly the five commands the sprint scope calls for:
`--help` (automatic), `doctor`, `plugins list`, `runtime info`,
`config validate`. Every command constructs its own ephemeral Runtime for
the duration of the invocation and tears it down before exiting — Sprint 1
has no long-running daemon/IPC layer (see the top-level implementation
summary's Sprint 2 backlog).
"""

from __future__ import annotations

import json as json_module
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer

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
