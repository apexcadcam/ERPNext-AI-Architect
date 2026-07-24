"""The Connector Contract: the one fixed declaration schema every Connector
implements, regardless of `target_system_type`.

Implements SPRINT3_ARCHITECTURE_PACKAGE.md §6.1 in full. Ten declarations
are named there; nine are data fields on `ConnectorManifest`/
`ConnectorOperation` below. The tenth — Version Awareness — is explicitly
**not applicable** here: §6.1 states it outright ("a live Connector call has
no equivalent [to a crawled document's version-confidence banding]... the
live system's own current state *is* the answer"), so, per this project's
"state absence explicitly, never leave a section silently blank" discipline
(`docs/crawler/SOURCE_CONNECTOR_SPEC.md § 1`'s own stated convention), that
absence is documented here rather than represented as an empty field.

A manifest is pure data — loaded from a `connector.yaml` file discovered by
the nested `ConnectorRegistry` (registry.py) — never hand-constructed for a
specific, hardcoded connector, mirroring `runtime/modules/manifest.py`'s
identical discipline for Module manifests, one level down.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from integration.errors import ConnectorManifestError

#: §6.1 declaration 1: `target_system_type` is open-ended — "one of
#: [these], or a newly-registered kind the moment one is needed" — so this
#: is documentation of the currently-anticipated values, never an enum
#: enforced by the schema.
KNOWN_TARGET_SYSTEM_TYPES = (
    "erpnext-site",
    "mcp-server",
    "git-hosting-api",
    "container-runtime",
    "relational-database",
    "filesystem",
    "browser-automation",
)


class ConnectorOperation(BaseModel):
    """One entry in §6.1 declaration 4's Operation Catalog, carrying
    declaration 5 (Request/Response Shape) and declaration 8
    (Destructive-Operation Gating) as its own per-operation fields — both
    are scoped to one operation, not the connector as a whole.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="The capability string this operation is resolved by.")
    kind: Literal["read", "write"]
    idempotent: bool

    #: §6.1 declaration 5 — opaque to the Runtime and to this contract;
    #: meaningful only to the connector and its caller.
    request_shape_ref: str = ""
    response_shape_ref: str = ""

    #: §6.1 declaration 8. `None` means "not explicitly set by the
    #: manifest" — `requires_confirmation` below computes the correct
    #: default from `kind`/`idempotent` in that case, per §6.1's own text:
    #: "defaults requires_confirmation: true [for write+non-idempotent]
    #: unless the connector's manifest explicitly, individually
    #: overrides it."
    requires_confirmation_override: bool | None = None
    confirmation_scope: Literal["per-call", "per-session", "never-required"] = "never-required"

    @property
    def requires_confirmation(self) -> bool:
        """§6.1 declaration 8's computed default: every `write` operation
        that is not `idempotent` requires confirmation unless the manifest
        explicitly overrides it either way.
        """

        if self.requires_confirmation_override is not None:
            return self.requires_confirmation_override
        return self.kind == "write" and not self.idempotent

    @property
    def capability(self) -> str:
        """The capability string §6.3 resolves by — this operation's own
        `name`. Connector authors are expected to namespace it themselves
        (e.g. `"erpnext.read_record"`, per §6.3's own examples) — nothing
        in this contract auto-prefixes it with `connector_id`, which is
        exactly what makes two connectors accidentally declaring the same
        operation name a genuine, detectable ambiguous-capability
        condition (registry.py), not a structural impossibility.
        """

        return self.name


class ConnectorManifest(BaseModel):
    """See SPRINT3_ARCHITECTURE_PACKAGE.md §6.1 for the meaning of every
    field below, grouped by the declaration it implements.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # -- §6.1 declaration 1: Identity -----------------------------------
    connector_id: str = Field(min_length=1, description="Stable, permanent — never reassigned or reused.")
    display_name: str = Field(min_length=1)
    maintained_by: str = Field(min_length=1)
    target_system_type: str = Field(min_length=1)
    version: str = Field(min_length=1)

    # -- §6.1 declaration 2: Authentication -------------------------------
    auth_required: bool = False
    auth_method: Literal["none", "api_key", "oauth_token", "basic", "mtls", "session_token"] = "none"
    #: Per SPRINT3_ARCHITECTURE_PACKAGE.md §8: never a literal secret, only
    #: a `scheme://key` pointer. This contract does not resolve it — see
    #: §5.3/§14: a connector resolves its own credentials only via the
    #: Secrets Resolver, never by any other path, and never inside this
    #: manifest layer.
    credential_reference: str | None = None

    # -- §6.1 declaration 3: Connection Parameters ------------------------
    endpoint_kind: Literal["url", "socket", "stdio", "local_path"]
    endpoint_reference: str = Field(min_length=1)

    # -- §6.1 declaration 4: Operation Catalog ----------------------------
    operations: tuple[ConnectorOperation, ...] = ()

    # -- §6.1 declaration 6: Rate Limits -----------------------------------
    requests_per_second: float | None = None
    concurrency_limit: int | None = None
    respects_platform_headers: bool = False

    # -- §6.1 declaration 7: Retries ------------------------------------------
    max_attempts: int = Field(default=1, ge=1)
    backoff_kind: Literal["exponential"] = "exponential"
    base_delay_ms: int = Field(default=0, ge=0)
    retryable_status_codes: tuple[int, ...] = ()

    #: Dynamic-loading convention, mirroring
    #: `runtime.modules.manifest.ModuleManifest.entry_point` exactly:
    #: `'<python_module_name>:<factory_function>'` inside the connector's
    #: own directory, resolved by `ConnectorRegistry.instantiate()`.
    entry_point: str

    @field_validator("entry_point")
    @classmethod
    def _entry_point_has_colon(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("entry_point must be formatted as 'module_name:factory_function'")
        return value

    @field_validator("operations")
    @classmethod
    def _operation_names_unique_within_one_manifest(
        cls, value: tuple[ConnectorOperation, ...]
    ) -> tuple[ConnectorOperation, ...]:
        names = [operation.name for operation in value]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate operation names within one connector manifest: {names}")
        return value

    @property
    def entry_module_name(self) -> str:
        return self.entry_point.split(":", 1)[0]

    @property
    def entry_factory_name(self) -> str:
        return self.entry_point.split(":", 1)[1]

    @property
    def provided_capabilities(self) -> frozenset[str]:
        """Every capability this connector's Operation Catalog exposes —
        §6.3's resolution unit. Empty for a connector with no operations
        yet, the same "structurally valid to provide nothing" state
        `docs/studio/STUDIO_ARCHITECTURE.md §4` already establishes for a
        Module providing zero capabilities.
        """

        return frozenset(operation.capability for operation in self.operations)


def load_connector_manifest(path: Path) -> ConnectorManifest:
    """Load and validate one `connector.yaml` file.

    Mirrors `runtime.modules.manifest.load_manifest`'s discipline exactly:
    a manifest that fails to parse is a registration-blocking error for
    that connector, raised here, never swallowed or defaulted.
    """

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConnectorManifestError(f"could not read connector manifest {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConnectorManifestError(f"malformed YAML in connector manifest {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConnectorManifestError(f"connector manifest {path} must contain a mapping at the top level")

    try:
        return ConnectorManifest(**data)
    except Exception as exc:  # pydantic.ValidationError and friends
        raise ConnectorManifestError(f"connector manifest {path} failed schema validation: {exc}") from exc


class ConnectorRequest(BaseModel):
    """SPRINT3_ARCHITECTURE_PACKAGE.md §6.2's Connector Request/Response
    Envelope — designed there, implemented here (Sprint 5, closing
    `ADR-0009`'s C1 finding). The one fixed shape every Connector operation
    is invoked through, regardless of `target_system_type`.

    `operation` names the same capability string `ConnectorOperation.name`/
    `.capability` already declares (§6.3) — a connector's `invoke()` (see
    `integration.lifecycle.ConnectorLifecycle`) dispatches on this field.
    `parameters` is opaque to this contract, per §6.1 declaration 5 —
    meaningful only to the connector and its caller.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)


class ConnectorResponse(BaseModel):
    """SPRINT3_ARCHITECTURE_PACKAGE.md §6.2's Connector Request/Response
    Envelope, response half. `result` is opaque, per the same §6.1
    declaration 5 discipline as `ConnectorRequest.parameters`. `diagnostics`
    never carries a literal secret (§8.5, inherited unmodified).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["success", "failure", "partial"]
    result: dict[str, Any] = Field(default_factory=dict)
    diagnostics: str = ""
    correlation_id: str = Field(min_length=1)
