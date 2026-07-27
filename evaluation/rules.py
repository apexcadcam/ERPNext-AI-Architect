"""Architecture Evaluation's own rule engine.

Implements Architecture Evaluation Engine Specification v1.0 §5, plus the
Threshold Documentation & Rule Metadata Addendum, in full: twelve
deterministic rules, each a pure function `(RepositoryFacts, FactIndex) ->
Finding | None`, reading its own thresholds by name from `RULE_THRESHOLDS`
rather than embedding a magic number in its own algorithm.

**Why zero rules use reasoning:** every one of the thirteen named
responsibility areas turned out to be expressible as a deterministic
count/ratio/presence check over `RepositoryFacts`' own real fields. Using
a Reasoning Engine anywhere here would be in direct tension with the
Critical Design Principle ("every score must be reproducible") since a
real LLM's output is not deterministic given fixed input. See the
specification's own "LLM Usage" section for the full argument.

**Architectural boundaries and layering are not covered by a dedicated
rule** (disclosed in the specification's §1 and §5): `ComponentFact.
component_kind`/`EntryPointFact.entry_kind`/`ServiceFact.service_kind` are
each single-valued in the real, frozen Synthesis v1.1 output today (only
`"doctype"`/`"frappe_app_entry"`/`"scheduled_task"` exist) -- there is no
cross-kind boundary to check yet.

Evidence lists are capped at `_MAX_EVIDENCE_ITEMS` entries per finding to
keep the artifact bounded on large repositories -- `Finding.metric_value`
always reflects the true, uncapped count; only the evidence *sample* is
capped, disclosed here rather than silently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from synthesis.contract import (
    ApiFact,
    ComponentFact,
    ConfigurationFact,
    DependencyFact,
    EntryPointFact,
    ExtensionPointFact,
    ModuleFact,
    RepositoryFacts,
    ServiceFact,
    UnresolvedFact,
)

from evaluation.contract import Confidence, Evidence, Finding, RuleThresholdSpec, Severity

#: Bounds the evidence sample per finding -- disclosed, not a threshold to
#: calibrate (it bounds artifact size, not rule-firing behavior).
_MAX_EVIDENCE_ITEMS = 20

_AnyFact = (
    ModuleFact
    | ComponentFact
    | ApiFact
    | ServiceFact
    | ConfigurationFact
    | DependencyFact
    | ExtensionPointFact
    | EntryPointFact
    | UnresolvedFact
)

# -- Rule Metadata Registry -- Threshold Documentation & Rule Metadata Addendum ----------------------

RULE_THRESHOLDS: tuple[RuleThresholdSpec, ...] = (
    RuleThresholdSpec(
        rule_id="MOD-002",
        threshold_name="share_medium",
        value=0.8,
        calibration_status="heuristic_default",
        justification=(
            "80/20-style dominant-partition heuristic; not measured against real repository data "
            "(Synthesis has only run against small synthetic test fixtures so far)."
        ),
    ),
    RuleThresholdSpec(
        rule_id="MOD-002",
        threshold_name="share_high",
        value=0.95,
        calibration_status="heuristic_default",
        justification="Near-total concentration (effectively no second module); same caveat as share_medium.",
    ),
    RuleThresholdSpec(
        rule_id="MOD-002",
        threshold_name="min_total_facts",
        value=10.0,
        calibration_status="heuristic_default",
        justification=(
            "Floor to avoid a false positive on a trivially small repository (e.g. 2 facts, 1 module = "
            "meaningless '100% concentration'). The need for a floor is justified; the exact number isn't."
        ),
    ),
    RuleThresholdSpec(
        rule_id="COH-001",
        threshold_name="ratio_medium",
        value=0.2,
        calibration_status="heuristic_default",
        justification="More than 1-in-5 facts outside any known module is a meaningful minority; unvalidated.",
    ),
    RuleThresholdSpec(
        rule_id="COH-001",
        threshold_name="ratio_high",
        value=0.5,
        calibration_status="heuristic_default",
        justification="Majority of facts outside module boundaries; a structurally severe signal; unvalidated.",
    ),
    RuleThresholdSpec(
        rule_id="EXT-002",
        threshold_name="ratio_medium",
        value=0.3,
        calibration_status="heuristic_default",
        justification=(
            "Already a proxy metric at MEDIUM confidence in the specification -- this threshold sits on top "
            "of an indirect measurement, the weakest-justified rule in the table."
        ),
    ),
    RuleThresholdSpec(
        rule_id="EXT-002",
        threshold_name="ratio_high",
        value=0.6,
        calibration_status="heuristic_default",
        justification="Same proxy-metric caveat as ratio_medium.",
    ),
    RuleThresholdSpec(
        rule_id="DEP-001",
        threshold_name="count_medium",
        value=30.0,
        calibration_status="heuristic_default",
        justification=(
            "Round order-of-magnitude number -- first calibration priority, since raw dependency count is "
            "the easiest threshold to validate empirically once run against a real repository."
        ),
    ),
    RuleThresholdSpec(
        rule_id="DEP-001",
        threshold_name="count_high",
        value=60.0,
        calibration_status="heuristic_default",
        justification="Same as count_medium.",
    ),
    RuleThresholdSpec(
        rule_id="DEP-002",
        threshold_name="ratio_medium",
        value=0.5,
        calibration_status="heuristic_default",
        justification="Half or more dependencies unpinned is a real reproducibility risk in principle; unvalidated.",
    ),
    RuleThresholdSpec(
        rule_id="DEP-002",
        threshold_name="ratio_high",
        value=0.8,
        calibration_status="heuristic_default",
        justification="Version pinning effectively absent; unvalidated.",
    ),
    RuleThresholdSpec(
        rule_id="DEP-002",
        threshold_name="min_total_dependencies",
        value=5.0,
        calibration_status="heuristic_default",
        justification="Floor to avoid a false positive on a very small dependency list.",
    ),
    RuleThresholdSpec(
        rule_id="CFG-001",
        threshold_name="missing_medium",
        value=2.0,
        calibration_status="heuristic_default",
        justification=(
            "Two or more missing baseline keys suggests hooks.py was never fully filled in. The rule's own "
            "premise (which keys count as 'baseline') is an editorial choice, not a Frappe framework "
            "requirement -- flagged for review alongside the threshold."
        ),
    ),
    RuleThresholdSpec(
        rule_id="API-001",
        threshold_name="ratio_medium",
        value=15.0,
        calibration_status="heuristic_default",
        justification="Round number with no empirical basis at all -- the least-grounded numeric choice.",
    ),
    RuleThresholdSpec(
        rule_id="API-001",
        threshold_name="ratio_high",
        value=30.0,
        calibration_status="heuristic_default",
        justification="Same as ratio_medium.",
    ),
    RuleThresholdSpec(
        rule_id="SVC-001",
        threshold_name="count_medium",
        value=20.0,
        calibration_status="heuristic_default",
        justification="Round, unvalidated number.",
    ),
    RuleThresholdSpec(
        rule_id="SVC-001",
        threshold_name="count_high",
        value=40.0,
        calibration_status="heuristic_default",
        justification="Same as count_medium.",
    ),
    RuleThresholdSpec(
        rule_id="MNT-001",
        threshold_name="ratio_medium",
        value=0.05,
        calibration_status="empirical",
        justification=(
            "Sprint 16 production validation observed error_count: 0 across all three real repositories "
            "(Apex Dashboard, ERPNext, Frappe) -- 5% is a generous margin above an actually-observed 0% "
            "baseline, not an arbitrary pick."
        ),
    ),
    RuleThresholdSpec(
        rule_id="MNT-001",
        threshold_name="ratio_high",
        value=0.2,
        calibration_status="empirical",
        justification=(
            "Clear deviation from the observed 0% baseline -- though this grounding is inherited from "
            "Discovery's own validation, not Synthesis's, since Synthesis has not itself been run against "
            "real repository data."
        ),
    ),
)


def get_threshold(rule_id: str, threshold_name: str) -> float:
    for spec in RULE_THRESHOLDS:
        if spec.rule_id == rule_id and spec.threshold_name == threshold_name:
            return spec.value
    raise KeyError(f"no threshold registered for {rule_id}.{threshold_name}")


# -- Stage 1: Fact Indexing -----------------------------------------------------------------------


@dataclass(frozen=True)
class FactIndex:
    """Package-internal. Built once per evaluation, shared by every rule,
    so no rule re-derives module ownership independently.
    """

    modules_by_prefix_length: tuple[ModuleFact, ...]  # sorted longest relative_path first

    def owning_module(self, relative_path: str) -> str | None:
        for module in self.modules_by_prefix_length:
            prefix = module.relative_path
            if relative_path == prefix or relative_path.startswith(prefix + "/"):
                return module.name
        return None


def build_fact_index(facts: RepositoryFacts) -> FactIndex:
    return FactIndex(
        modules_by_prefix_length=tuple(
            sorted(facts.modules, key=lambda module: len(module.relative_path), reverse=True)
        )
    )


# -- Shared, deterministic evidence/summary helpers ------------------------------------------------


def _fact_summary(fact: _AnyFact) -> str:
    if isinstance(fact, ModuleFact):
        return f"{fact.module_kind}: {fact.name}"
    if isinstance(fact, ComponentFact):
        return f"{fact.component_kind}: {fact.name}"
    if isinstance(fact, ApiFact):
        return f"{fact.api_kind}: {fact.name}"
    if isinstance(fact, ServiceFact):
        return f"{fact.service_kind} (via {fact.declared_via}): {fact.name}"
    if isinstance(fact, ConfigurationFact):
        return f"{fact.key}={fact.value}"
    if isinstance(fact, DependencyFact):
        suffix = f" {fact.version_constraint}" if fact.version_constraint else " (unconstrained)"
        return f"{fact.dependency_kind} dependency: {fact.name}{suffix}"
    if isinstance(fact, ExtensionPointFact):
        return f"{fact.extension_kind}: {fact.name}"
    if isinstance(fact, EntryPointFact):
        return f"{fact.entry_kind}: {fact.name}"
    return f"unresolved: {fact.reason}"  # UnresolvedFact


def _evidence_for(fact: _AnyFact) -> Evidence:
    return Evidence(
        fact_kind=type(fact).__name__, fact_summary=_fact_summary(fact), relative_path=fact.relative_path
    )


def _affected_files(evidence: tuple[Evidence, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.relative_path for item in evidence}))


def _affected_modules(index: FactIndex, affected_files: tuple[str, ...]) -> tuple[str, ...]:
    owners = {index.owning_module(path) for path in affected_files}
    return tuple(sorted(owner for owner in owners if owner is not None))


def _evidence_tuple(facts_seq: list[_AnyFact]) -> tuple[Evidence, ...]:
    return tuple(_evidence_for(fact) for fact in facts_seq[:_MAX_EVIDENCE_ITEMS])


# -- MOD-001: No Modules Identified -------------------------------------------------------------------


def evaluate_no_modules_identified(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    orphaned: list[_AnyFact] = [*facts.components, *facts.apis, *facts.services]
    if len(facts.modules) != 0 or not orphaned:
        return None
    evidence = _evidence_tuple(orphaned)
    return Finding(
        rule_id="MOD-001",
        rule_name="No Modules Identified",
        category="modularity",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        metric_value=float(len(orphaned)),
        explanation=(
            f"{len(orphaned)} component/API/service fact(s) were identified but zero modules were "
            "recognized in this repository."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=(),
    )


# -- MOD-002: Single Dominant Module -------------------------------------------------------------------


def evaluate_single_dominant_module(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    if len(facts.modules) <= 1:
        return None
    all_facts: list[_AnyFact] = [*facts.components, *facts.apis, *facts.services]
    total = len(all_facts)
    if total < get_threshold("MOD-002", "min_total_facts"):
        return None

    counts: dict[str, int] = {}
    for fact in all_facts:
        owner = index.owning_module(fact.relative_path)
        if owner is not None:
            counts[owner] = counts.get(owner, 0) + 1
    if not counts:
        return None

    dominant_module, dominant_count = max(counts.items(), key=lambda item: item[1])
    share = dominant_count / total
    share_medium = get_threshold("MOD-002", "share_medium")
    if share <= share_medium:
        return None
    severity = Severity.HIGH if share >= get_threshold("MOD-002", "share_high") else Severity.MEDIUM

    dominant_facts = [
        fact for fact in all_facts if index.owning_module(fact.relative_path) == dominant_module
    ]
    evidence = _evidence_tuple(dominant_facts)
    return Finding(
        rule_id="MOD-002",
        rule_name="Single Dominant Module",
        category="modularity",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=share,
        explanation=(
            f"Module '{dominant_module}' accounts for {dominant_count} of {total} identified "
            f"components/APIs/services ({share:.0%}), exceeding the {share_medium:.0%} "
            "single-module concentration threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=(dominant_module,),
    )


# -- COH-001: Facts Outside Module Boundaries -----------------------------------------------------------


def evaluate_facts_outside_module_boundaries(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    all_facts: list[_AnyFact] = [*facts.components, *facts.apis, *facts.services]
    total = len(all_facts)
    if total == 0:
        return None
    unowned = [fact for fact in all_facts if index.owning_module(fact.relative_path) is None]
    ratio = len(unowned) / total
    ratio_medium = get_threshold("COH-001", "ratio_medium")
    if ratio <= ratio_medium:
        return None
    severity = Severity.HIGH if ratio >= get_threshold("COH-001", "ratio_high") else Severity.MEDIUM
    evidence = _evidence_tuple(unowned)
    return Finding(
        rule_id="COH-001",
        rule_name="Facts Outside Module Boundaries",
        category="cohesion",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=ratio,
        explanation=(
            f"{len(unowned)} of {total} identified components/APIs/services ({ratio:.0%}) do not fall "
            f"under any identified module's path, exceeding the {ratio_medium:.0%} threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=(),
    )


# -- EXT-001: External Framework Method Override --------------------------------------------------------


def evaluate_external_framework_override(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    own_module_names = {module.name for module in facts.modules}
    external = [
        ext
        for ext in facts.extension_points
        if ext.extension_kind == "override_whitelisted_method"
        and ext.name.split(".")[0] not in own_module_names
        and ext.name.split(".")[0] != ""
    ]
    if not external:
        return None
    evidence = _evidence_tuple(list(external))
    namespaces = sorted({ext.name.split(".")[0] for ext in external})
    own_names = ", ".join(sorted(own_module_names)) or "none identified"
    return Finding(
        rule_id="EXT-001",
        rule_name="External Framework Method Override",
        category="extension_mechanisms",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        metric_value=float(len(external)),
        explanation=(
            f"{len(external)} extension point(s) override a method outside this repository's own "
            f"modules ({own_names}): external namespace(s) {', '.join(namespaces)}."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- EXT-002: High Extension Point Density -----------------------------------------------------------


def evaluate_high_extension_point_density(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    denominator = max(1, len(facts.components) + len(facts.apis))
    ratio = len(facts.extension_points) / denominator
    ratio_medium = get_threshold("EXT-002", "ratio_medium")
    if ratio <= ratio_medium:
        return None
    severity = Severity.HIGH if ratio >= get_threshold("EXT-002", "ratio_high") else Severity.MEDIUM
    evidence = _evidence_tuple(list(facts.extension_points))
    return Finding(
        rule_id="EXT-002",
        rule_name="High Extension Point Density",
        category="extension_mechanisms",
        severity=severity,
        confidence=Confidence.MEDIUM,
        metric_value=ratio,
        explanation=(
            f"{len(facts.extension_points)} extension points relative to {denominator} components/APIs "
            f"(ratio {ratio:.2f}) exceeds the {ratio_medium:.2f} density threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- DEP-001: High External Dependency Count ----------------------------------------------------------


def evaluate_high_dependency_count(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    count = len(facts.dependencies)
    count_medium = get_threshold("DEP-001", "count_medium")
    if count <= count_medium:
        return None
    severity = Severity.HIGH if count >= get_threshold("DEP-001", "count_high") else Severity.MEDIUM
    evidence = _evidence_tuple(list(facts.dependencies))
    return Finding(
        rule_id="DEP-001",
        rule_name="High External Dependency Count",
        category="dependency_structure",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=float(count),
        explanation=(
            f"{count} external dependencies identified, exceeding the {count_medium:.0f}-dependency threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- DEP-002: Unconstrained Dependency Versions --------------------------------------------------------


def evaluate_unconstrained_dependency_versions(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    total = len(facts.dependencies)
    if total < get_threshold("DEP-002", "min_total_dependencies"):
        return None
    unconstrained = [dep for dep in facts.dependencies if not dep.version_constraint]
    ratio = len(unconstrained) / total
    ratio_medium = get_threshold("DEP-002", "ratio_medium")
    if ratio <= ratio_medium:
        return None
    severity = Severity.HIGH if ratio >= get_threshold("DEP-002", "ratio_high") else Severity.MEDIUM
    evidence = _evidence_tuple(list(unconstrained))
    return Finding(
        rule_id="DEP-002",
        rule_name="Unconstrained Dependency Versions",
        category="dependency_structure",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=ratio,
        explanation=(
            f"{len(unconstrained)} of {total} dependencies ({ratio:.0%}) have no version constraint, "
            f"exceeding the {ratio_medium:.0%} threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- CFG-001: Incomplete Baseline App Configuration -----------------------------------------------------

_BASELINE_CONFIG_KEYS = ("app_title", "app_publisher", "app_license")


def evaluate_incomplete_baseline_configuration(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    frappe_apps = [module for module in facts.modules if module.module_kind == "frappe_app"]
    evidence_list: list[Evidence] = []
    for module in frappe_apps:
        hooks_path = f"{module.relative_path}/hooks.py"
        present_keys = {cfg.key for cfg in facts.configuration if cfg.relative_path == hooks_path}
        for key in _BASELINE_CONFIG_KEYS:
            if key not in present_keys:
                evidence_list.append(
                    Evidence(
                        fact_kind="ConfigurationFact",
                        fact_summary=f"missing baseline key: {key}",
                        relative_path=hooks_path,
                    )
                )
    if not evidence_list:
        return None
    missing_total = len(evidence_list)
    severity = (
        Severity.MEDIUM if missing_total >= get_threshold("CFG-001", "missing_medium") else Severity.LOW
    )
    evidence = tuple(evidence_list[:_MAX_EVIDENCE_ITEMS])
    return Finding(
        rule_id="CFG-001",
        rule_name="Incomplete Baseline App Configuration",
        category="configuration_quality",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=float(missing_total),
        explanation=(
            f"{missing_total} baseline configuration key instance(s) missing across "
            f"{len(frappe_apps)} identified frappe_app module(s) (expected: {', '.join(_BASELINE_CONFIG_KEYS)})."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- API-001: Broad Whitelisted API Surface --------------------------------------------------------------


def evaluate_broad_api_surface(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    denominator = max(1, len(facts.modules))
    ratio = len(facts.apis) / denominator
    ratio_medium = get_threshold("API-001", "ratio_medium")
    if ratio <= ratio_medium:
        return None
    severity = Severity.HIGH if ratio >= get_threshold("API-001", "ratio_high") else Severity.MEDIUM
    evidence = _evidence_tuple(list(facts.apis))
    return Finding(
        rule_id="API-001",
        rule_name="Broad Whitelisted API Surface",
        category="api_exposure",
        severity=severity,
        confidence=Confidence.MEDIUM,
        metric_value=ratio,
        explanation=(
            f"{len(facts.apis)} whitelisted API(s) across {denominator} module(s) (ratio {ratio:.1f}) "
            f"exceeds the {ratio_medium:.0f}-per-module threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- SVC-001: High Scheduled Task Volume -----------------------------------------------------------------


def evaluate_high_scheduled_task_volume(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    scheduled = [service for service in facts.services if service.service_kind == "scheduled_task"]
    count = len(scheduled)
    count_medium = get_threshold("SVC-001", "count_medium")
    if count <= count_medium:
        return None
    severity = Severity.HIGH if count >= get_threshold("SVC-001", "count_high") else Severity.MEDIUM
    evidence = _evidence_tuple(list(scheduled))
    return Finding(
        rule_id="SVC-001",
        rule_name="High Scheduled Task Volume",
        category="service_organization",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=float(count),
        explanation=(
            f"{count} scheduled task(s) identified, exceeding the {count_medium:.0f}-task threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- MNT-001: High Unresolved Extraction Ratio -----------------------------------------------------------


def evaluate_high_unresolved_ratio(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    denominator = max(1, facts.statistics.files_examined)
    ratio = len(facts.unresolved) / denominator
    ratio_medium = get_threshold("MNT-001", "ratio_medium")
    if ratio <= ratio_medium:
        return None
    severity = Severity.HIGH if ratio >= get_threshold("MNT-001", "ratio_high") else Severity.MEDIUM
    evidence = _evidence_tuple(list(facts.unresolved))
    return Finding(
        rule_id="MNT-001",
        rule_name="High Unresolved Extraction Ratio",
        category="maintainability_indicators",
        severity=severity,
        confidence=Confidence.HIGH,
        metric_value=ratio,
        explanation=(
            f"{len(facts.unresolved)} of {denominator} examined files ({ratio:.0%}) could not be parsed "
            f"by Requirement Synthesis, exceeding the {ratio_medium:.0%} threshold."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- FWK-001: No Recognized Framework Module ---------------------------------------------------------------


def evaluate_no_recognized_framework_module(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
    if len(facts.modules) == 0:
        return None
    if any(module.module_kind == "frappe_app" for module in facts.modules):
        return None
    evidence = _evidence_tuple(list(facts.modules))
    return Finding(
        rule_id="FWK-001",
        rule_name="No Recognized Framework Module",
        category="framework_usage",
        severity=Severity.INFO,
        confidence=Confidence.HIGH,
        metric_value=float(len(facts.modules)),
        explanation=(
            f"{len(facts.modules)} Python package module(s) identified, none classified as a "
            "recognized framework (frappe_app) entry -- informational, not necessarily a defect."
        ),
        evidence=evidence,
        affected_files=_affected_files(evidence),
        affected_modules=_affected_modules(index, _affected_files(evidence)),
    )


# -- Registration, in fixed rule_id order (determinism: §2's own contract) ---------------------------

ALL_RULES: tuple[tuple[str, Callable[[RepositoryFacts, FactIndex], Finding | None]], ...] = (
    ("API-001", evaluate_broad_api_surface),
    ("CFG-001", evaluate_incomplete_baseline_configuration),
    ("COH-001", evaluate_facts_outside_module_boundaries),
    ("DEP-001", evaluate_high_dependency_count),
    ("DEP-002", evaluate_unconstrained_dependency_versions),
    ("EXT-001", evaluate_external_framework_override),
    ("EXT-002", evaluate_high_extension_point_density),
    ("FWK-001", evaluate_no_recognized_framework_module),
    ("MNT-001", evaluate_high_unresolved_ratio),
    ("MOD-001", evaluate_no_modules_identified),
    ("MOD-002", evaluate_single_dominant_module),
    ("SVC-001", evaluate_high_scheduled_task_volume),
)
