"""Tests for `evaluation.rules` (Architecture Evaluation Engine Specification v1.0 §5,
plus the Threshold Documentation & Rule Metadata Addendum)."""

from __future__ import annotations

import pytest

from synthesis.contract import (
    ApiFact,
    ComponentFact,
    ConfigurationFact,
    DependencyFact,
    ExtensionPointFact,
    ExtractionMethod,
    ModuleFact,
    RepositoryFacts,
    ServiceFact,
    SynthesisStatistics,
    UnresolvedFact,
)

from synthesis.contract import EntryPointFact

from evaluation.contract import Confidence, Severity
from evaluation.rules import (
    ALL_RULES,
    RULE_THRESHOLDS,
    FactIndex,
    _evidence_for,
    build_fact_index,
    evaluate_broad_api_surface,
    evaluate_external_framework_override,
    evaluate_facts_outside_module_boundaries,
    evaluate_high_dependency_count,
    evaluate_high_extension_point_density,
    evaluate_high_scheduled_task_volume,
    evaluate_high_unresolved_ratio,
    evaluate_incomplete_baseline_configuration,
    evaluate_no_modules_identified,
    evaluate_no_recognized_framework_module,
    evaluate_single_dominant_module,
    evaluate_unconstrained_dependency_versions,
    get_threshold,
)

# -- Fixture builders --------------------------------------------------------------------------------


def _facts(
    *,
    modules: tuple[ModuleFact, ...] = (),
    components: tuple[ComponentFact, ...] = (),
    apis: tuple[ApiFact, ...] = (),
    services: tuple[ServiceFact, ...] = (),
    configuration: tuple[ConfigurationFact, ...] = (),
    dependencies: tuple[DependencyFact, ...] = (),
    extension_points: tuple[ExtensionPointFact, ...] = (),
    unresolved: tuple[UnresolvedFact, ...] = (),
    files_examined: int = 100,
) -> RepositoryFacts:
    return RepositoryFacts(
        facts_id="facts-1",
        source_inventory_id="inv-1",
        repository_root="/repo",
        synthesized_at="2026-07-27T11:00:00+00:00",
        correlation_id="corr-1",
        modules=modules,
        components=components,
        apis=apis,
        services=services,
        configuration=configuration,
        dependencies=dependencies,
        extension_points=extension_points,
        entry_points=(),
        unresolved=unresolved,
        truncated=False,
        statistics=SynthesisStatistics(
            files_examined=files_examined, files_skipped=0, files_failed=len(unresolved), facts_extracted=0
        ),
    )


def _module(name: str, kind: str = "frappe_app", path: str | None = None) -> ModuleFact:
    return ModuleFact(
        name=name,
        relative_path=path or name,
        module_kind=kind,
        detection_method=ExtractionMethod.DETERMINISTIC,
    )


def _component(name: str, path: str) -> ComponentFact:
    return ComponentFact(
        name=name,
        relative_path=path,
        component_kind="doctype",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )


def _api(name: str, path: str) -> ApiFact:
    return ApiFact(
        name=name,
        relative_path=path,
        api_kind="whitelisted_method",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )


def _service(name: str, path: str, kind: str = "scheduled_task") -> ServiceFact:
    return ServiceFact(
        name=name,
        relative_path=path,
        service_kind=kind,
        declared_via="scheduler_events",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )


def _config(key: str, path: str, value: str = "x") -> ConfigurationFact:
    return ConfigurationFact(
        key=key, value=value, relative_path=path, detection_method=ExtractionMethod.DETERMINISTIC
    )


def _dependency(name: str, path: str, constraint: str = "") -> DependencyFact:
    return DependencyFact(
        name=name,
        version_constraint=constraint,
        relative_path=path,
        dependency_kind="python",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )


def _extension(name: str, path: str, kind: str = "override_whitelisted_method") -> ExtensionPointFact:
    return ExtensionPointFact(
        name=name, relative_path=path, extension_kind=kind, detection_method=ExtractionMethod.DETERMINISTIC
    )


def _unresolved(path: str) -> UnresolvedFact:
    return UnresolvedFact(relative_path=path, reason="parse error")


def _index(facts: RepositoryFacts) -> FactIndex:
    return build_fact_index(facts)


# -- _evidence_for / _fact_summary (shared helper) ------------------------------------------------
#
# ConfigurationFact and EntryPointFact are never passed through this shared
# dispatcher by any of the 12 registered rules today (CFG-001 builds its
# own Evidence directly for missing keys; no rule inspects entry_points
# individually yet) -- tested directly here rather than left uncovered,
# since the dispatcher itself is real, correct, shared code, not dead
# speculative generality.


def test_evidence_for_summarizes_a_configuration_fact() -> None:
    evidence = _evidence_for(_config("app_title", "app/hooks.py", value="My App"))
    assert evidence.fact_kind == "ConfigurationFact"
    assert evidence.fact_summary == "app_title=My App"


def test_evidence_for_summarizes_an_entry_point_fact() -> None:
    entry = EntryPointFact(
        name="hooks.py",
        relative_path="app/hooks.py",
        entry_kind="frappe_app_entry",
        detection_method=ExtractionMethod.DETERMINISTIC,
    )
    evidence = _evidence_for(entry)
    assert evidence.fact_kind == "EntryPointFact"
    assert evidence.fact_summary == "frappe_app_entry: hooks.py"


# -- get_threshold / RULE_THRESHOLDS -----------------------------------------------------------------


def test_get_threshold_returns_the_registered_value() -> None:
    assert get_threshold("MOD-002", "share_medium") == 0.8


def test_get_threshold_raises_for_an_unregistered_threshold() -> None:
    with pytest.raises(KeyError):
        get_threshold("MOD-002", "does_not_exist")


def test_every_rule_threshold_references_a_real_registered_rule_id() -> None:
    real_rule_ids = {rule_id for rule_id, _ in ALL_RULES}
    for spec in RULE_THRESHOLDS:
        assert spec.rule_id in real_rule_ids


def test_every_threshold_calibration_status_is_a_documented_value() -> None:
    assert {spec.calibration_status for spec in RULE_THRESHOLDS} <= {"empirical", "heuristic_default"}


def test_mnt_001_thresholds_are_the_only_empirically_calibrated_ones() -> None:
    empirical = {
        (spec.rule_id, spec.threshold_name)
        for spec in RULE_THRESHOLDS
        if spec.calibration_status == "empirical"
    }
    assert empirical == {("MNT-001", "ratio_medium"), ("MNT-001", "ratio_high")}


# -- ALL_RULES registration -----------------------------------------------------------------------


def test_all_rules_has_exactly_twelve_entries() -> None:
    assert len(ALL_RULES) == 12


def test_all_rules_is_sorted_by_rule_id() -> None:
    rule_ids = [rule_id for rule_id, _ in ALL_RULES]
    assert rule_ids == sorted(rule_ids)


def test_all_rules_has_no_duplicate_rule_ids() -> None:
    rule_ids = [rule_id for rule_id, _ in ALL_RULES]
    assert len(rule_ids) == len(set(rule_ids))


# -- FactIndex -------------------------------------------------------------------------------------


def test_fact_index_resolves_a_file_directly_under_a_module() -> None:
    facts = _facts(modules=(_module("apex_dashboard"),))
    index = _index(facts)
    assert index.owning_module("apex_dashboard/hooks.py") == "apex_dashboard"


def test_fact_index_returns_none_for_an_unowned_path() -> None:
    facts = _facts(modules=(_module("apex_dashboard"),))
    index = _index(facts)
    assert index.owning_module("scripts/run.py") is None


def test_fact_index_uses_longest_prefix_match() -> None:
    facts = _facts(
        modules=(_module("app", path="app"), _module("app.sub", kind="python_package", path="app/sub"))
    )
    index = _index(facts)
    assert index.owning_module("app/sub/thing.py") == "app.sub"
    assert index.owning_module("app/other.py") == "app"


# -- MOD-001 ----------------------------------------------------------------------------------------


def test_mod_001_fires_when_content_exists_with_no_modules() -> None:
    facts = _facts(components=(_component("X", "app/doctype/x/x.json"),))
    finding = evaluate_no_modules_identified(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH
    assert finding.confidence is Confidence.HIGH
    assert finding.metric_value == 1.0


def test_mod_001_does_not_fire_on_a_genuinely_empty_repository() -> None:
    facts = _facts()
    assert evaluate_no_modules_identified(facts, _index(facts)) is None


def test_mod_001_does_not_fire_when_a_module_exists() -> None:
    facts = _facts(modules=(_module("app"),), components=(_component("X", "app/doctype/x/x.json"),))
    assert evaluate_no_modules_identified(facts, _index(facts)) is None


# -- MOD-002 ----------------------------------------------------------------------------------------


def test_mod_002_fires_medium_at_90_percent_concentration() -> None:
    modules = (_module("a", path="a"), _module("b", path="b"))
    components = tuple(_component(f"C{i}", f"a/doctype/c{i}/c{i}.json") for i in range(9)) + (
        _component("D", "b/doctype/d/d.json"),
    )
    facts = _facts(modules=modules, components=components)
    finding = evaluate_single_dominant_module(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM
    assert finding.metric_value == pytest.approx(0.9)
    assert finding.affected_modules == ("a",)


def test_mod_002_fires_high_at_95_percent_concentration() -> None:
    modules = (_module("a", path="a"), _module("b", path="b"))
    components = tuple(_component(f"C{i}", f"a/doctype/c{i}/c{i}.json") for i in range(19)) + (
        _component("D", "b/doctype/d/d.json"),
    )
    facts = _facts(modules=modules, components=components)
    finding = evaluate_single_dominant_module(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


def test_mod_002_does_not_fire_below_min_total_facts() -> None:
    modules = (_module("a", path="a"), _module("b", path="b"))
    components = tuple(_component(f"C{i}", f"a/doctype/c{i}/c{i}.json") for i in range(8)) + (
        _component("D", "b/doctype/d/d.json"),
    )
    facts = _facts(modules=modules, components=components)
    assert evaluate_single_dominant_module(facts, _index(facts)) is None


def test_mod_002_does_not_fire_with_a_single_module() -> None:
    facts = _facts(
        modules=(_module("a"),), components=tuple(_component(f"C{i}", f"a/x{i}.json") for i in range(10))
    )
    assert evaluate_single_dominant_module(facts, _index(facts)) is None


def test_mod_002_does_not_fire_when_all_facts_are_unowned() -> None:
    modules = (_module("a", path="a"), _module("b", path="b"))
    components = tuple(_component(f"C{i}", f"elsewhere/x{i}.json") for i in range(10))
    facts = _facts(modules=modules, components=components)
    assert evaluate_single_dominant_module(facts, _index(facts)) is None


def test_mod_002_does_not_fire_when_concentration_is_below_the_threshold() -> None:
    modules = (_module("a", path="a"), _module("b", path="b"))
    components = tuple(_component(f"C{i}", f"a/x{i}.json") for i in range(5)) + tuple(
        _component(f"D{i}", f"b/x{i}.json") for i in range(5)
    )
    facts = _facts(modules=modules, components=components)
    assert evaluate_single_dominant_module(facts, _index(facts)) is None


# -- COH-001 ----------------------------------------------------------------------------------------


def test_coh_001_fires_medium_for_40_percent_unowned() -> None:
    facts = _facts(
        modules=(_module("a"),),
        components=(
            _component("C1", "a/x1.json"),
            _component("C2", "a/x2.json"),
            _component("C3", "a/x3.json"),
            _component("C4", "other/x4.json"),
            _component("C5", "other/x5.json"),
        ),
    )
    finding = evaluate_facts_outside_module_boundaries(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM
    assert finding.metric_value == pytest.approx(0.4)


def test_coh_001_fires_high_for_60_percent_unowned() -> None:
    facts = _facts(
        modules=(_module("a"),),
        components=(
            _component("C1", "a/x1.json"),
            _component("C2", "other/x2.json"),
            _component("C3", "other/x3.json"),
        ),
    )
    finding = evaluate_facts_outside_module_boundaries(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


def test_coh_001_does_not_fire_when_all_facts_are_owned() -> None:
    facts = _facts(modules=(_module("a"),), components=(_component("C1", "a/x1.json"),))
    assert evaluate_facts_outside_module_boundaries(facts, _index(facts)) is None


def test_coh_001_does_not_fire_on_an_empty_fact_set() -> None:
    facts = _facts(modules=(_module("a"),))
    assert evaluate_facts_outside_module_boundaries(facts, _index(facts)) is None


# -- EXT-001 (the real Apex Dashboard scenario) -------------------------------------------------------


def test_ext_001_fires_for_the_real_apex_dashboard_override_scenario() -> None:
    facts = _facts(
        modules=(_module("apex_dashboard"),),
        extension_points=(_extension("frappe.desk.desktop.get_desktop_page", "apex_dashboard/hooks.py"),),
    )
    finding = evaluate_external_framework_override(facts, _index(facts))
    assert finding is not None
    assert finding.rule_id == "EXT-001"
    assert finding.severity is Severity.MEDIUM
    assert finding.confidence is Confidence.HIGH
    assert finding.metric_value == 1.0
    assert "frappe" in finding.explanation
    assert finding.affected_modules == ("apex_dashboard",)
    assert finding.evidence[0].relative_path == "apex_dashboard/hooks.py"


def test_ext_001_does_not_fire_for_an_internal_override() -> None:
    facts = _facts(
        modules=(_module("apex_dashboard"),),
        extension_points=(_extension("apex_dashboard.utils.some_internal_hook", "apex_dashboard/hooks.py"),),
    )
    assert evaluate_external_framework_override(facts, _index(facts)) is None


def test_ext_001_ignores_non_override_extension_kinds() -> None:
    facts = _facts(
        modules=(_module("apex_dashboard"),),
        extension_points=(
            _extension("Sales Invoice.on_submit", "apex_dashboard/hooks.py", kind="doc_event"),
        ),
    )
    assert evaluate_external_framework_override(facts, _index(facts)) is None


def test_ext_001_handles_a_name_with_a_leading_dot_without_crashing() -> None:
    facts = _facts(extension_points=(_extension(".weird", "hooks.py"),))
    # A leading-dot name has an empty first segment -- must not be treated as
    # an "external" match against nothing.
    assert evaluate_external_framework_override(facts, _index(facts)) is None


# -- EXT-002 ----------------------------------------------------------------------------------------


def test_ext_002_fires_medium_at_half_density() -> None:
    facts = _facts(
        components=(_component("A", "a.json"), _component("B", "b.json")),
        extension_points=(_extension("x.y", "hooks.py"),),
    )
    finding = evaluate_high_extension_point_density(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM
    assert finding.confidence is Confidence.MEDIUM


def test_ext_002_fires_high_at_full_density() -> None:
    facts = _facts(
        components=(_component("A", "a.json"), _component("B", "b.json")),
        extension_points=(_extension("x.y", "hooks.py"), _extension("x.z", "hooks.py")),
    )
    finding = evaluate_high_extension_point_density(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


def test_ext_002_does_not_fire_with_no_extension_points() -> None:
    facts = _facts(components=(_component("A", "a.json"),))
    assert evaluate_high_extension_point_density(facts, _index(facts)) is None


# -- DEP-001 ----------------------------------------------------------------------------------------


def test_dep_001_does_not_fire_at_exactly_the_threshold() -> None:
    facts = _facts(dependencies=tuple(_dependency(f"pkg{i}", "pyproject.toml") for i in range(30)))
    assert evaluate_high_dependency_count(facts, _index(facts)) is None


def test_dep_001_fires_medium_just_above_the_threshold() -> None:
    facts = _facts(dependencies=tuple(_dependency(f"pkg{i}", "pyproject.toml") for i in range(31)))
    finding = evaluate_high_dependency_count(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM


def test_dep_001_fires_high_at_the_high_threshold() -> None:
    facts = _facts(dependencies=tuple(_dependency(f"pkg{i}", "pyproject.toml") for i in range(60)))
    finding = evaluate_high_dependency_count(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


# -- DEP-002 ----------------------------------------------------------------------------------------


def test_dep_002_does_not_fire_below_min_total_dependencies() -> None:
    facts = _facts(dependencies=tuple(_dependency(f"pkg{i}", "pyproject.toml") for i in range(4)))
    assert evaluate_unconstrained_dependency_versions(facts, _index(facts)) is None


def test_dep_002_fires_medium_at_60_percent_unconstrained() -> None:
    deps = tuple(_dependency(f"pkg{i}", "pyproject.toml", constraint="") for i in range(3)) + tuple(
        _dependency(f"pkg{i}", "pyproject.toml", constraint=">=1.0") for i in range(2)
    )
    facts = _facts(dependencies=deps)
    finding = evaluate_unconstrained_dependency_versions(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM
    assert finding.metric_value == pytest.approx(0.6)


def test_dep_002_fires_high_at_80_percent_unconstrained() -> None:
    deps = tuple(_dependency(f"pkg{i}", "pyproject.toml", constraint="") for i in range(4)) + (
        _dependency("pinned", "pyproject.toml", constraint=">=1.0"),
    )
    facts = _facts(dependencies=deps)
    finding = evaluate_unconstrained_dependency_versions(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


def test_dep_002_does_not_fire_when_most_dependencies_are_pinned() -> None:
    deps = tuple(_dependency(f"pkg{i}", "pyproject.toml", constraint=">=1.0") for i in range(5))
    facts = _facts(dependencies=deps)
    assert evaluate_unconstrained_dependency_versions(facts, _index(facts)) is None


# -- CFG-001 ----------------------------------------------------------------------------------------


def test_cfg_001_does_not_fire_when_all_baseline_keys_present() -> None:
    facts = _facts(
        modules=(_module("app"),),
        configuration=(
            _config("app_title", "app/hooks.py"),
            _config("app_publisher", "app/hooks.py"),
            _config("app_license", "app/hooks.py"),
        ),
    )
    assert evaluate_incomplete_baseline_configuration(facts, _index(facts)) is None


def test_cfg_001_fires_low_for_one_missing_key() -> None:
    facts = _facts(
        modules=(_module("app"),),
        configuration=(_config("app_title", "app/hooks.py"), _config("app_publisher", "app/hooks.py")),
    )
    finding = evaluate_incomplete_baseline_configuration(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.LOW
    assert finding.metric_value == 1.0


def test_cfg_001_fires_medium_for_two_or_more_missing_keys() -> None:
    facts = _facts(modules=(_module("app"),), configuration=())
    finding = evaluate_incomplete_baseline_configuration(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM
    assert finding.metric_value == 3.0


def test_cfg_001_does_not_fire_with_no_frappe_app_modules() -> None:
    facts = _facts(modules=(_module("app", kind="python_package"),), configuration=())
    assert evaluate_incomplete_baseline_configuration(facts, _index(facts)) is None


# -- API-001 ----------------------------------------------------------------------------------------


def test_api_001_does_not_fire_at_exactly_the_threshold() -> None:
    facts = _facts(modules=(_module("app"),), apis=tuple(_api(f"fn{i}", "app/x.py") for i in range(15)))
    assert evaluate_broad_api_surface(facts, _index(facts)) is None


def test_api_001_fires_medium_just_above_the_threshold() -> None:
    facts = _facts(modules=(_module("app"),), apis=tuple(_api(f"fn{i}", "app/x.py") for i in range(16)))
    finding = evaluate_broad_api_surface(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM
    assert finding.confidence is Confidence.MEDIUM


def test_api_001_fires_high_at_the_high_threshold() -> None:
    facts = _facts(modules=(_module("app"),), apis=tuple(_api(f"fn{i}", "app/x.py") for i in range(30)))
    finding = evaluate_broad_api_surface(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


# -- SVC-001 ----------------------------------------------------------------------------------------


def test_svc_001_does_not_fire_at_exactly_the_threshold() -> None:
    facts = _facts(services=tuple(_service(f"task{i}", "app/hooks.py") for i in range(20)))
    assert evaluate_high_scheduled_task_volume(facts, _index(facts)) is None


def test_svc_001_fires_medium_just_above_the_threshold() -> None:
    facts = _facts(services=tuple(_service(f"task{i}", "app/hooks.py") for i in range(21)))
    finding = evaluate_high_scheduled_task_volume(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM


def test_svc_001_fires_high_at_the_high_threshold() -> None:
    facts = _facts(services=tuple(_service(f"task{i}", "app/hooks.py") for i in range(40)))
    finding = evaluate_high_scheduled_task_volume(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


def test_svc_001_ignores_non_scheduled_task_service_kinds() -> None:
    facts = _facts(services=tuple(_service(f"task{i}", "app/hooks.py", kind="other_kind") for i in range(25)))
    assert evaluate_high_scheduled_task_volume(facts, _index(facts)) is None


# -- MNT-001 ----------------------------------------------------------------------------------------


def test_mnt_001_does_not_fire_at_exactly_the_threshold() -> None:
    facts = _facts(unresolved=tuple(_unresolved(f"bad{i}.py") for i in range(5)), files_examined=100)
    assert evaluate_high_unresolved_ratio(facts, _index(facts)) is None


def test_mnt_001_fires_medium_just_above_the_threshold() -> None:
    facts = _facts(unresolved=tuple(_unresolved(f"bad{i}.py") for i in range(6)), files_examined=100)
    finding = evaluate_high_unresolved_ratio(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.MEDIUM


def test_mnt_001_fires_high_at_the_high_threshold() -> None:
    facts = _facts(unresolved=tuple(_unresolved(f"bad{i}.py") for i in range(20)), files_examined=100)
    finding = evaluate_high_unresolved_ratio(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


def test_mnt_001_handles_zero_files_examined_without_crashing() -> None:
    facts = _facts(unresolved=(_unresolved("bad.py"),), files_examined=0)
    finding = evaluate_high_unresolved_ratio(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.HIGH


# -- FWK-001 ----------------------------------------------------------------------------------------


def test_fwk_001_fires_when_only_python_packages_are_identified() -> None:
    facts = _facts(modules=(_module("lib", kind="python_package"),))
    finding = evaluate_no_recognized_framework_module(facts, _index(facts))
    assert finding is not None
    assert finding.severity is Severity.INFO


def test_fwk_001_does_not_fire_when_a_frappe_app_is_identified() -> None:
    facts = _facts(modules=(_module("app", kind="frappe_app"), _module("app.sub", kind="python_package")))
    assert evaluate_no_recognized_framework_module(facts, _index(facts)) is None


def test_fwk_001_does_not_fire_with_no_modules_at_all() -> None:
    facts = _facts()
    assert evaluate_no_recognized_framework_module(facts, _index(facts)) is None
