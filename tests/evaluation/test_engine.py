"""Tests for `evaluation.engine` (Architecture Evaluation Engine Specification v1.0 §2, §4, §7)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from discovery.contract import DiscoveryRequest
from discovery.engine import discover_repository
from synthesis.contract import RepositoryFacts, SynthesisRequest
from synthesis.engine import synthesize_requirements

from evaluation.contract import EvaluationRequest, Finding, Severity
from evaluation.engine import Budget, assemble_evaluation, evaluate_architecture, execute_rules
from evaluation.rules import ALL_RULES, FactIndex, build_fact_index

# -- Fixture -- a real Frappe-app-shaped tree, chained through all three real engines ------------------

_HOOKS_PY = """
app_name = "apex_dashboard"
scheduler_events = {
    "daily": ["apex_dashboard.tasks.clear_cache"],
}
override_whitelisted_methods = {
    "frappe.desk.desktop.get_desktop_page": "apex_dashboard.overrides.get_desktop_page_override",
}
"""

_OVERRIDES_PY = """
import frappe


@frappe.whitelist()
@frappe.read_only()
def get_desktop_page_override(page):
    return {}
"""


def _build_apex_dashboard_like_app(root: Path) -> None:
    app = root / "apex_dashboard"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "hooks.py").write_text(_HOOKS_PY)
    (app / "overrides.py").write_text(_OVERRIDES_PY)


def _real_evaluation_request(root: Path, **overrides: object) -> EvaluationRequest:
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(root), correlation_id="c", requested_by="r")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="c", requested_by="r")
    )
    defaults: dict[str, object] = {
        "repository_facts": facts,
        "correlation_id": "corr-1",
        "requested_by": "test-suite",
    }
    defaults.update(overrides)
    return EvaluationRequest(**defaults)  # type: ignore[arg-type]


# -- end to end, through the real Discovery -> Synthesis -> Evaluation chain ---------------------------


def test_evaluate_architecture_end_to_end_through_the_real_engine_chain(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    request = _real_evaluation_request(tmp_path)

    evaluation = evaluate_architecture(request)

    assert evaluation.source_facts_id == request.repository_facts.facts_id
    assert evaluation.repository_root == str(tmp_path)
    assert evaluation.truncated is False
    assert evaluation.skipped_rules == ()
    assert evaluation.statistics.rules_evaluated == len(ALL_RULES)

    ext_001 = next(f for f in evaluation.findings if f.rule_id == "EXT-001")
    assert ext_001.severity is Severity.MEDIUM
    assert "frappe" in ext_001.explanation
    assert ext_001.affected_modules == ("apex_dashboard",)


def test_evaluate_architecture_reproduces_the_real_apex_dashboard_finding_manually(tmp_path: Path) -> None:
    # Explainability requirement: another engineer must be able to reproduce
    # a finding manually using only RepositoryFacts and the documented rule.
    _build_apex_dashboard_like_app(tmp_path)
    request = _real_evaluation_request(tmp_path)
    evaluation = evaluate_architecture(request)
    ext_001 = next(f for f in evaluation.findings if f.rule_id == "EXT-001")

    facts = request.repository_facts
    own_module_names = {m.name for m in facts.modules}
    external = [
        e
        for e in facts.extension_points
        if e.extension_kind == "override_whitelisted_method" and e.name.split(".")[0] not in own_module_names
    ]

    assert len(external) == ext_001.metric_value


# -- Determinism -----------------------------------------------------------------------------------


def test_evaluate_architecture_is_deterministic_across_repeated_runs(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    request = _real_evaluation_request(tmp_path)

    first = evaluate_architecture(request)
    second = evaluate_architecture(request)

    strip = {"evaluation_id": "x", "evaluated_at": "x"}
    assert first.model_copy(update=strip) == second.model_copy(update=strip)


# -- execute_rules / SkippedRule on a raising rule -----------------------------------------------------


def test_execute_rules_records_a_raising_rule_as_skipped_without_aborting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import evaluation.rules as rules_module

    def _broken_rule(facts: RepositoryFacts, index: FactIndex) -> Finding | None:
        raise ValueError("deliberately broken for this test")

    patched_rules = tuple(
        (rule_id, _broken_rule) if rule_id == "MOD-001" else (rule_id, rule_fn)
        for rule_id, rule_fn in ALL_RULES
    )
    monkeypatch.setattr(rules_module, "ALL_RULES", patched_rules)
    import evaluation.engine as engine_module

    monkeypatch.setattr(engine_module, "ALL_RULES", patched_rules)

    _build_apex_dashboard_like_app(tmp_path)
    request = _real_evaluation_request(tmp_path)

    evaluation = evaluate_architecture(request)

    assert any(s.rule_id == "MOD-001" for s in evaluation.skipped_rules)
    assert evaluation.statistics.rules_skipped == 1
    # every other rule still ran -- the broken one didn't abort the run
    assert any(f.rule_id == "EXT-001" for f in evaluation.findings)


# -- Budget truncation --------------------------------------------------------------------------------


def test_execute_rules_truncates_at_max_findings(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    request = _real_evaluation_request(tmp_path, max_findings=2)

    facts = request.repository_facts
    index = build_fact_index(facts)
    budget = Budget(remaining_rules=2, deadline=time.monotonic() + 30.0)
    findings, skipped = execute_rules(facts, index, budget)

    assert budget.truncated is True
    evaluation = assemble_evaluation(request, findings, skipped, budget)
    assert evaluation.truncated is True
    assert evaluation.statistics.rules_evaluated == 2


def test_evaluate_architecture_propagates_repository_facts_truncated_flag(tmp_path: Path) -> None:
    _build_apex_dashboard_like_app(tmp_path)
    inventory = discover_repository(
        DiscoveryRequest(repository_root=str(tmp_path), correlation_id="c", requested_by="r")
    )
    facts = synthesize_requirements(
        SynthesisRequest(repository_inventory=inventory, correlation_id="c", requested_by="r")
    )
    truncated_facts = facts.model_copy(update={"truncated": True})
    request = EvaluationRequest(repository_facts=truncated_facts, correlation_id="c", requested_by="r")

    evaluation = evaluate_architecture(request)

    assert evaluation.truncated is True
