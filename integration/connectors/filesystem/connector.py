"""The Filesystem Connector — Sprint 3, Phase 4.

The architectural reference implementation of a concrete Connector: the
first real proof that the Phase 3 framework (Connector Contract +
Lifecycle + Registry) works end to end, chosen as the lowest-risk possible
target (no network, no credential, no live external service).

Deliberately minimal, per this phase's own scope — four operations only:
`read_text`, `write_text`, `exists`, `list_directory`. No recursive copy,
no delete-tree, no move, no permissions, no watches. This connector is not
a general-purpose filesystem abstraction; it exists to be structurally
identical to what future connectors (ERPNext, GitHub, Docker, ...) will
look like, not to be featureful.

No ERP-specific concepts, no planner logic, no knowledge-graph logic:
every method here is a plain, generic filesystem primitive.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from integration.contract import ConnectorManifest, ConnectorRequest, ConnectorResponse
from integration.errors import ConnectorLifecycleError
from integration.lifecycle import ConnectorHealth, ConnectorLifecycle


class FilesystemConnector(ConnectorLifecycle):
    """Every operation is resolved beneath the manifest's own
    `endpoint_reference` — this connector's configured root — never an
    arbitrary absolute path elsewhere on the host. This containment check
    is the one guardrail Phase 4 implements; it is not a general sandbox
    (no defense against e.g. symlinks placed inside the root that point
    back out), which would be exactly the kind of "feature-rich" scope
    this phase explicitly avoids.
    """

    def __init__(self, manifest: ConnectorManifest) -> None:
        super().__init__(manifest)
        self._root: Path | None = None

    # -- Lifecycle -----------------------------------------------------------

    def connect(self) -> None:
        root = Path(self.manifest.endpoint_reference).expanduser().resolve()
        if not root.is_dir():
            raise ConnectorLifecycleError(
                f"filesystem connector's endpoint_reference '{root}' is not an existing directory"
            )
        self._root = root

    def disconnect(self) -> None:
        self._root = None

    def health_check(self) -> ConnectorHealth:
        if self._root is None:
            return ConnectorHealth(healthy=False, detail="not connected")
        if not self._root.is_dir():
            return ConnectorHealth(healthy=False, detail=f"root '{self._root}' no longer exists")
        return ConnectorHealth(healthy=True, detail=f"root '{self._root}' reachable")

    # -- Operations ------------------------------------------------------------

    def read_text(self, path: str) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"no such file: '{path}'")
        return target.read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> None:
        """Destructive: overwrites (or creates) the target file. Declared
        in connector.yaml as `kind: write, idempotent: false` with no
        `requires_confirmation_override` — it participates in the
        Connector Contract's existing default gating
        (`ConnectorOperation.requires_confirmation`) rather than bypassing
        it.
        """

        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def list_directory(self, path: str = ".") -> tuple[str, ...]:
        target = self._resolve(path)
        if not target.is_dir():
            raise NotADirectoryError(f"not a directory: '{path}'")
        return tuple(sorted(entry.name for entry in target.iterdir()))

    # -- Invocation envelope (Sprint 5, Phase 1) --------------------------------

    def invoke(self, request: ConnectorRequest) -> ConnectorResponse:
        """Dispatches `request.operation` to the matching method above.
        Mirrors Sprint 5 Architecture Package §9.1: an ordinary operational
        failure (missing file, invalid path, bad parameters) becomes a
        `status="failure"` response, never a raised exception; only a
        `ConnectorLifecycleError` (not connected) propagates, since that is
        a lifecycle-contract violation, not an operational outcome.
        """

        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "filesystem.read_text": self._invoke_read_text,
            "filesystem.write_text": self._invoke_write_text,
            "filesystem.exists": self._invoke_exists,
            "filesystem.list_directory": self._invoke_list_directory,
        }
        handler = handlers.get(request.operation)
        if handler is None:
            return ConnectorResponse(
                status="failure",
                diagnostics=f"unknown operation '{request.operation}'",
                correlation_id=request.correlation_id,
            )

        try:
            result = handler(request.parameters)
        except ConnectorLifecycleError:
            raise
        except Exception as exc:
            return ConnectorResponse(
                status="failure", diagnostics=str(exc), correlation_id=request.correlation_id
            )
        return ConnectorResponse(status="success", result=result, correlation_id=request.correlation_id)

    def _invoke_read_text(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"content": self.read_text(parameters["path"])}

    def _invoke_write_text(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self.write_text(parameters["path"], parameters["content"])
        return {}

    def _invoke_exists(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"exists": self.exists(parameters["path"])}

    def _invoke_list_directory(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"entries": self.list_directory(parameters.get("path", "."))}

    # -- internals ---------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        if self._root is None:
            raise ConnectorLifecycleError("filesystem connector used before connect() succeeded")
        candidate = (self._root / path).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ValueError(f"path '{path}' escapes the connector's configured root")
        return candidate


def create(manifest: ConnectorManifest) -> FilesystemConnector:
    return FilesystemConnector(manifest)
