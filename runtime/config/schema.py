"""Configuration schema: the Runtime-defaults layer and shared validation rules.

Per docs/runtime/CONFIGURATION_SYSTEM.md §2, the lowest-precedence layer is
"Runtime defaults" — built-in, safe fallback values shipped with the Runtime
itself, so a completely empty configuration directory still boots to a
conservative, working state. Every other layer (Global, Environment, Module,
Pipeline, Connector) only ever *overrides* a subset of these keys.
"""

from __future__ import annotations

import enum
import re

from pydantic import BaseModel, ConfigDict, Field

#: The current configuration schema version. A MAJOR bump requires every
#: stored layer to be explicitly migrated or re-validated, never silently
#: reinterpreted under a new meaning (CONFIGURATION_SYSTEM.md §5).
CONFIG_SCHEMA_VERSION = "1.0.0"

#: Key-name patterns that must never carry a literal value — only a
#: `credential_reference`-shaped one (CONFIGURATION_SYSTEM.md §6,
#: SOURCE_CONNECTOR_SPEC.md §1.2). Deliberately conservative: false positives
#: (rejecting a legitimate non-secret key) are far cheaper than the failure
#: mode this check exists to prevent.
_CREDENTIAL_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|credential|private[_-]?key)", re.IGNORECASE
)
#: A value is treated as a safe *reference* to a credential, never the
#: credential itself, only if it carries this prefix.
_CREDENTIAL_REFERENCE_PREFIX = "ref:"


class ConfigLayer(enum.Enum):
    """The six layers, in ascending precedence order (CONFIGURATION_SYSTEM.md §2)."""

    RUNTIME_DEFAULT = "runtime_default"
    GLOBAL = "global"
    ENVIRONMENT = "environment"
    MODULE = "module"
    PIPELINE = "pipeline"
    CONNECTOR = "connector"


#: Precedence order lowest -> highest, single source of truth for the merge
#: order used everywhere else in this package.
LAYER_PRECEDENCE: tuple[ConfigLayer, ...] = (
    ConfigLayer.RUNTIME_DEFAULT,
    ConfigLayer.GLOBAL,
    ConfigLayer.ENVIRONMENT,
    ConfigLayer.MODULE,
    ConfigLayer.PIPELINE,
    ConfigLayer.CONNECTOR,
)


class RuntimeDefaults(BaseModel):
    """The built-in, safe fallback configuration (ConfigLayer.RUNTIME_DEFAULT).

    Every field here has a value — an empty configuration directory still
    produces a fully-specified, working configuration.
    """

    model_config = ConfigDict(frozen=True)

    config_schema_version: str = CONFIG_SCHEMA_VERSION
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "json"
    plugin_discovery_paths: tuple[str, ...] = ()
    boot_health_check_timeout_seconds: float = 5.0
    event_bus_default_queue_size: int = 1000


def is_credential_shaped_key(key: str) -> bool:
    """Whether a config key name looks like it should hold a secret."""

    return bool(_CREDENTIAL_KEY_PATTERN.search(key))


def is_safe_credential_reference(value: object) -> bool:
    """Whether a value is a `ref:`-prefixed pointer rather than a literal secret."""

    return isinstance(value, str) and value.startswith(_CREDENTIAL_REFERENCE_PREFIX)


class ConfigValidationIssue(BaseModel):
    """One schema or policy violation found while validating a config layer."""

    layer: ConfigLayer
    scope: str | None = Field(
        default=None, description="e.g. the module_id/pipeline name/connector_id this layer is scoped to"
    )
    key: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        scope_part = f"[{self.scope}]" if self.scope else ""
        return f"{self.layer.value}{scope_part}.{self.key}: {self.message}"
