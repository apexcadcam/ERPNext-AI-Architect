"""Plugin entry point for the Extractor module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point` factory.
The actual behavior lives in knowledge/extraction/, a proper importable
package — never duplicated here.
"""

from __future__ import annotations

from knowledge.extraction import ExtractorModule
from runtime.modules.manifest import ModuleManifest


def create(manifest: ModuleManifest) -> ExtractorModule:
    return ExtractorModule(manifest)
