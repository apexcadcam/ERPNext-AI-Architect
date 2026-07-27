"""Plugin entry point for the Synthesis module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point`
factory. The actual behavior lives in synthesis/, a proper importable
package — never duplicated here.
"""

from __future__ import annotations

from runtime.modules.manifest import ModuleManifest

from synthesis.module import SynthesisModule


def create(manifest: ModuleManifest) -> SynthesisModule:
    return SynthesisModule(manifest)
