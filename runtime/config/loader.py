"""Hierarchical configuration loading and resolution.

Implements docs/runtime/CONFIGURATION_SYSTEM.md: six layers, inheritance
(a key not set at a layer falls through to the next-less-specific one, down
to Runtime defaults), and validation before any module reaches init().

Layout on disk (a directory convention, matching the same "no hardcoded
imports" discipline the Plugin Registry uses for module discovery):

    <config_dir>/
        global.yaml
        environments/<name>.yaml
        modules/<module_id>.yaml
        pipelines/<pipeline_name>.yaml
        connectors/<connector_id>.yaml

Every file is optional — an absent file contributes nothing to that layer,
which is a normal, expected state (CONFIGURATION_SYSTEM.md §3), never an
error. A *present but malformed* file is a ConfigurationError.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from runtime.config.schema import (
    ConfigLayer,
    ConfigValidationIssue,
    RuntimeDefaults,
    is_credential_shaped_key,
    is_safe_credential_reference,
)
from runtime.errors import ConfigurationError


@dataclass(frozen=True)
class ResolvedConfig:
    """The result of merging every applicable layer for one resolution scope."""

    values: dict[str, Any]
    #: Which layer ultimately supplied each key, for diagnostics
    #: (`architect config validate`, `architect runtime info`).
    provenance: dict[str, ConfigLayer]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __contains__(self, key: str) -> bool:
        return key in self.values


def _read_yaml_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"could not read configuration file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"malformed YAML in configuration file {path}: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(
            f"configuration file {path} must contain a mapping at the top level, got {type(data).__name__}"
        )
    return data


def _validate_no_literal_credentials(
    values: dict[str, Any], layer: ConfigLayer, scope: str | None
) -> list[ConfigValidationIssue]:
    """CONFIGURATION_SYSTEM.md §6: reject any literal-looking secret value."""

    issues: list[ConfigValidationIssue] = []
    for key, value in values.items():
        if is_credential_shaped_key(key) and not is_safe_credential_reference(value):
            issues.append(
                ConfigValidationIssue(
                    layer=layer,
                    scope=scope,
                    key=key,
                    message=(
                        "key name looks credential-shaped but its value is not a "
                        "'ref:'-prefixed credential_reference; literal secrets are "
                        "never permitted in configuration"
                    ),
                )
            )
    return issues


class ConfigLoader:
    """Loads and resolves the six-layer configuration hierarchy."""

    def __init__(self, config_dir: Path | str, environment: str | None = None) -> None:
        self.config_dir = Path(config_dir)
        self._runtime_defaults = RuntimeDefaults()
        self.environment = environment or self._runtime_defaults.environment

    # -- per-layer loading -------------------------------------------------

    def load_global(self) -> dict[str, Any]:
        path = self.config_dir / "global.yaml"
        return _read_yaml_file(path) if path.is_file() else {}

    def load_environment(self) -> dict[str, Any]:
        path = self.config_dir / "environments" / f"{self.environment}.yaml"
        return _read_yaml_file(path) if path.is_file() else {}

    def load_module(self, module_id: str) -> dict[str, Any]:
        path = self.config_dir / "modules" / f"{module_id}.yaml"
        return _read_yaml_file(path) if path.is_file() else {}

    def load_pipeline(self, pipeline_name: str) -> dict[str, Any]:
        path = self.config_dir / "pipelines" / f"{pipeline_name}.yaml"
        return _read_yaml_file(path) if path.is_file() else {}

    def load_connector(self, connector_id: str) -> dict[str, Any]:
        path = self.config_dir / "connectors" / f"{connector_id}.yaml"
        return _read_yaml_file(path) if path.is_file() else {}

    # -- validation ----------------------------------------------------------

    def validate(
        self,
        *,
        module_id: str | None = None,
        pipeline_name: str | None = None,
        connector_id: str | None = None,
    ) -> list[ConfigValidationIssue]:
        """Validate every applicable layer. Never raises — callers decide
        whether a non-empty result is boot-blocking (RUNTIME_BOOT_SEQUENCE.md
        §4) or merely reported (`architect config validate`).
        """

        issues: list[ConfigValidationIssue] = []

        try:
            RuntimeDefaults()
        except ValidationError as exc:  # pragma: no cover - defaults are static and known-good
            issues.append(
                ConfigValidationIssue(
                    layer=ConfigLayer.RUNTIME_DEFAULT, scope=None, key="<schema>", message=str(exc)
                )
            )

        layered: list[tuple[ConfigLayer, str | None, dict[str, Any]]] = [
            (ConfigLayer.GLOBAL, None, self.load_global()),
            (ConfigLayer.ENVIRONMENT, self.environment, self.load_environment()),
        ]
        if module_id is not None:
            layered.append((ConfigLayer.MODULE, module_id, self.load_module(module_id)))
        if pipeline_name is not None:
            layered.append((ConfigLayer.PIPELINE, pipeline_name, self.load_pipeline(pipeline_name)))
        if connector_id is not None:
            layered.append((ConfigLayer.CONNECTOR, connector_id, self.load_connector(connector_id)))

        for layer, scope, values in layered:
            issues.extend(_validate_no_literal_credentials(values, layer, scope))

        return issues

    # -- resolution ------------------------------------------------------

    def resolve(
        self,
        *,
        module_id: str | None = None,
        pipeline_name: str | None = None,
        connector_id: str | None = None,
        strict: bool = True,
    ) -> ResolvedConfig:
        """Merge every applicable layer, lowest to highest precedence.

        A key set at a more specific layer overrides a less specific one for
        that key only — the rest of the less-specific layer's keys are left
        untouched (CONFIGURATION_SYSTEM.md §2). If `strict`, raises
        ConfigurationError when `validate()` finds any issue; the CLI's
        `config validate` command instead calls `validate()` directly so it
        can report every issue rather than stopping at the first.
        """

        if strict:
            issues = self.validate(module_id=module_id, pipeline_name=pipeline_name, connector_id=connector_id)
            if issues:
                formatted = "\n".join(f"  - {issue}" for issue in issues)
                raise ConfigurationError(f"configuration validation failed:\n{formatted}")

        values: dict[str, Any] = self._runtime_defaults.model_dump()
        provenance: dict[str, ConfigLayer] = dict.fromkeys(values, ConfigLayer.RUNTIME_DEFAULT)

        layered: list[tuple[ConfigLayer, dict[str, Any]]] = [
            (ConfigLayer.GLOBAL, self.load_global()),
            (ConfigLayer.ENVIRONMENT, self.load_environment()),
        ]
        if module_id is not None:
            layered.append((ConfigLayer.MODULE, self.load_module(module_id)))
        if pipeline_name is not None:
            layered.append((ConfigLayer.PIPELINE, self.load_pipeline(pipeline_name)))
        if connector_id is not None:
            layered.append((ConfigLayer.CONNECTOR, self.load_connector(connector_id)))

        for layer, layer_values in layered:
            for key, value in layer_values.items():
                values[key] = value
                provenance[key] = layer

        return ResolvedConfig(values=values, provenance=provenance)
