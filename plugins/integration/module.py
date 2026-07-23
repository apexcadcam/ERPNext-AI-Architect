"""Plugin entry point for the Integration module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point` factory.
The actual behavior lives in integration/, a proper importable package —
never duplicated here.
"""

from __future__ import annotations

from integration import IntegrationModule
from runtime.modules.manifest import ModuleManifest


def create(manifest: ModuleManifest) -> IntegrationModule:
    return IntegrationModule(manifest)
