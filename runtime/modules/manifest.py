"""The Module Manifest: the one contract every module declares itself against.

Implements docs/runtime/MODULE_SYSTEM.md §2. A manifest is pure data —
loaded from a `module.yaml` file discovered by the Plugin Registry
(docs/runtime/PLUGIN_REGISTRY.md §1) — never hand-constructed by the
Runtime for a specific, hardcoded module.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from runtime.errors import ManifestError


class ModuleManifest(BaseModel):
    """See MODULE_SYSTEM.md §2 for the meaning of every field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module_id: str = Field(min_length=1, description="Stable, permanent — never reassigned or reused.")
    display_name: str = Field(min_length=1)
    maintained_by: str = Field(min_length=1)
    version: str = Field(min_length=1, description="Semver of this module's own manifest/behavior.")

    capabilities_provided: tuple[str, ...] = Field(default=())
    capabilities_required: tuple[str, ...] = Field(default=())
    pipeline_stage_bindings: tuple[str, ...] = Field(default=())
    events_published: tuple[str, ...] = Field(default=())
    events_subscribed: tuple[str, ...] = Field(default=())

    config_schema_ref: str | None = Field(
        default=None, description="Where this module's own configuration schema lives."
    )
    enabled_by_default: bool = Field(default=True)

    entry_point: str = Field(
        description=(
            "'<python_module_name>:<factory_function>' inside the plugin's own directory — "
            "resolved dynamically by the Plugin Registry via importlib, never a hardcoded "
            "import anywhere in the Runtime itself (PLUGIN_REGISTRY.md §1)."
        )
    )

    @field_validator("entry_point")
    @classmethod
    def _entry_point_has_colon(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("entry_point must be formatted as 'module_name:factory_function'")
        return value

    @property
    def entry_module_name(self) -> str:
        return self.entry_point.split(":", 1)[0]

    @property
    def entry_factory_name(self) -> str:
        return self.entry_point.split(":", 1)[1]


def load_manifest(path: Path) -> ModuleManifest:
    """Load and validate one `module.yaml` file.

    Per RUNTIME_BOOT_SEQUENCE.md §2: a manifest that fails to parse is a
    boot-blocking error — raised here as ManifestError, never swallowed or
    defaulted, because a malformed manifest's intended enabled/disabled
    state is itself unknown.
    """

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"could not read manifest {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ManifestError(f"malformed YAML in manifest {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"manifest {path} must contain a mapping at the top level")

    try:
        return ModuleManifest(**data)
    except Exception as exc:  # pydantic.ValidationError and friends
        raise ManifestError(f"manifest {path} failed schema validation: {exc}") from exc
