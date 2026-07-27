"""Requirement Synthesis — Sprint 17.

Implements the Requirement Synthesis Engine Specification v1.1 in full:
given an already-produced `discovery.contract.RepositoryInventory`,
extracts a deterministic set of structural facts about the repository —
modules, components, APIs, services, configuration, dependencies,
extension points, and runtime entry points — as one self-contained
`RepositoryFacts` artifact. Zero Reasoning Engine calls anywhere in this
package.

`RepositoryFacts` is not the same thing as `analysis.contract.Requirement`
— this package extracts structural facts only, never interpreted business
intent (see this package's own contract.py docstring).

Depends only on `discovery.contract` (for `RepositoryInventory`/
`RepositoryFileType`), `integration.contract`/
`integration.connectors.filesystem.connector` (for `FilesystemConnector`,
constructed directly, mirroring `discovery.engine.resolve_connector`'s own
precedent), and `runtime.pipeline.engine`/`runtime.modules.base`/
`runtime.modules.manifest`/`runtime.container.di`. Nothing in this package
imports `analysis/`, `knowledge/`, `intelligence/`, `planning/`,
`execution/`, `orchestration/`, or `composition_root/`.
"""

from __future__ import annotations

from synthesis.contract import (
    ApiFact,
    ComponentFact,
    ConfigurationFact,
    DependencyFact,
    EntryPointFact,
    ExtensionPointFact,
    ExtractionMethod,
    ModuleFact,
    RepositoryFacts,
    ServiceFact,
    SynthesisRequest,
    SynthesisStatistics,
    UnresolvedFact,
)
from synthesis.engine import synthesize_requirements
from synthesis.errors import RepositoryInventoryStaleError, SynthesisError_

__all__ = [
    "ApiFact",
    "ComponentFact",
    "ConfigurationFact",
    "DependencyFact",
    "EntryPointFact",
    "ExtensionPointFact",
    "ExtractionMethod",
    "ModuleFact",
    "RepositoryFacts",
    "RepositoryInventoryStaleError",
    "ServiceFact",
    "SynthesisError_",
    "SynthesisRequest",
    "SynthesisStatistics",
    "UnresolvedFact",
    "synthesize_requirements",
]
