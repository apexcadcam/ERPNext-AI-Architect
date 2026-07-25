"""Plugin entry point for the Execution module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point` factory.
The actual behavior lives in execution/, a proper importable package —
never duplicated here.
"""

from __future__ import annotations

from runtime.modules.manifest import ModuleManifest

from execution.module import ExecutionModule


def create(manifest: ModuleManifest) -> ExecutionModule:
    return ExecutionModule(manifest)
