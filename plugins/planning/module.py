"""Plugin entry point for the Planning module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point` factory.
The actual behavior lives in planning/, a proper importable package —
never duplicated here.
"""

from __future__ import annotations

from planning.module import PlanningModule
from runtime.modules.manifest import ModuleManifest


def create(manifest: ModuleManifest) -> PlanningModule:
    return PlanningModule(manifest)
