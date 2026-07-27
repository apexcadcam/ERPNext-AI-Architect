"""Requirement Synthesis's own contract: the one fixed set of types every
stage produces and consumes, and the final `RepositoryFacts` artifact
callers receive.

Implements Requirement Synthesis Engine Specification v1.1 §2 and §3 in
full. Every model is frozen, matching every other contract in this
project (`discovery.contract.RepositoryInventory`,
`integration.contract.ConnectorManifest`, ...).

**`RepositoryFacts` is not `analysis.contract.Requirement`.** That
existing, frozen type models business/domain analysis derived from
natural-language requirement text (entities, processes, rules).
`RepositoryFacts` models structural facts about source code (modules,
APIs, services, config, dependencies, extension points, entry points) --
a `DocType` named "Sales Invoice" is recorded here as a component named
"Sales Invoice"; this package never reasons about what a sales invoice
*is*. The two types share no relationship and this package never imports
`analysis/`.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field

from discovery.contract import RepositoryInventory

#: §2's Input defaults -- overridable per request, independent of
#: discovery.contract's own budget defaults (a separate budget for a
#: separate stage of work).
DEFAULT_MAX_FILES: int = 10_000
DEFAULT_TIMEOUT_SECONDS: float = 30.0


class ExtractionMethod(str, enum.Enum):
    """§4's disclosed extension point. `REASONING_ASSISTED` is defined but
    never produced by this version -- every fact this engine's supported
    scope (Python + Frappe/ERPNext conventions) extracts is a syntactic or
    schema fact, not a judgment, so deterministic extraction is sufficient
    and a Reasoning Engine call is never invoked. Reserved for a future
    sprint extending language coverage, mirroring
    `discovery.contract.RepositoryFileType.UNKNOWN`'s identical role as an
    honest fallback rather than a forced guess.
    """

    DETERMINISTIC = "deterministic"
    REASONING_ASSISTED = "reasoning_assisted"


class SynthesisRequest(BaseModel):
    """§2's Input. Wraps an already-produced `RepositoryInventory` --
    Synthesis never receives a raw path and never re-walks, re-classifies,
    or re-derives anything Discovery already computed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_inventory: RepositoryInventory
    correlation_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    max_files: int = Field(default=DEFAULT_MAX_FILES, ge=1)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)


class UnresolvedFact(BaseModel):
    """One path that failed extraction without aborting the whole run --
    §7's "partial synthesis" outcome, made visible rather than swallowed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ModuleFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    module_kind: str = Field(min_length=1)
    detection_method: ExtractionMethod


class ComponentFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    component_kind: str = Field(min_length=1)
    detection_method: ExtractionMethod


class ApiFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    signature: str = ""
    api_kind: str = Field(min_length=1)
    detection_method: ExtractionMethod


class ServiceFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    service_kind: str = Field(min_length=1)
    declared_via: str = Field(min_length=1)
    detection_method: ExtractionMethod


class ConfigurationFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    value: str = ""
    relative_path: str = Field(min_length=1)
    detection_method: ExtractionMethod


class DependencyFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    version_constraint: str = ""
    relative_path: str = Field(min_length=1)
    dependency_kind: str = Field(min_length=1)
    detection_method: ExtractionMethod


class ExtensionPointFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    extension_kind: str = Field(min_length=1)
    detection_method: ExtractionMethod


class EntryPointFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    entry_kind: str = Field(min_length=1)
    detection_method: ExtractionMethod


class SynthesisStatistics(BaseModel):
    """§3's deterministic, purely structural metadata -- counts only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    files_examined: int = Field(ge=0)
    files_skipped: int = Field(ge=0)
    files_failed: int = Field(ge=0)
    facts_extracted: int = Field(ge=0)


class RepositoryFacts(BaseModel):
    """§3's final artifact -- the one thing `synthesize_requirements()`
    returns. `source_inventory_id` gives traceability back to the exact
    `RepositoryInventory` these facts were derived from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    facts_id: str = Field(min_length=1)
    source_inventory_id: str = Field(min_length=1)
    repository_root: str = Field(min_length=1)
    synthesized_at: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    modules: tuple[ModuleFact, ...]
    components: tuple[ComponentFact, ...]
    apis: tuple[ApiFact, ...]
    services: tuple[ServiceFact, ...]
    configuration: tuple[ConfigurationFact, ...]
    dependencies: tuple[DependencyFact, ...]
    extension_points: tuple[ExtensionPointFact, ...]
    entry_points: tuple[EntryPointFact, ...]
    unresolved: tuple[UnresolvedFact, ...]
    truncated: bool
    statistics: SynthesisStatistics
