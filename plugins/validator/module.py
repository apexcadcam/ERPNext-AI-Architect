"""Plugin entry point for the Validator module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point` factory.
The actual behavior lives in knowledge/validation/, a proper importable
package — never duplicated here.
"""

from __future__ import annotations

from knowledge.validation import ValidatorModule
from runtime.modules.manifest import ModuleManifest


def create(manifest: ModuleManifest) -> ValidatorModule:
    return ValidatorModule(manifest)
