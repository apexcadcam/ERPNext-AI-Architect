"""Plugin entry point for the Aggregation module.

Thin, per docs/runtime/PLUGIN_REGISTRY.md §1: the Plugin Registry
dynamically imports this file and calls its declared `entry_point`
factory. The actual behavior lives in aggregation/, a proper importable
package — never duplicated here.
"""

from __future__ import annotations

from runtime.modules.manifest import ModuleManifest

from aggregation.module import AggregationModule


def create(manifest: ModuleManifest) -> AggregationModule:
    return AggregationModule(manifest)
