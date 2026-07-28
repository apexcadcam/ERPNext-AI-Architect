"""Tests for `evidence.collectors` (Evidence Extraction Engine Architecture Specification v1.1 §7)."""

from __future__ import annotations

import ast

from evidence.collectors import (
    _FileContext,
    _class_membership,
    _compute_evidence_id,
    _decorator_dotted_name,
    _dotted_name,
    _is_whitelist_decorator,
    _module_dotted_name,
    _qualified_symbol,
    collect_controller_lifecycle_hook_evidence,
    collect_whitelisted_api_decoration_evidence,
)
from evidence.contract import CanonicalRepository, CollectorName, EvidenceCategory


def _context(relative_path: str = "frappe/model/document.py") -> _FileContext:
    return _FileContext(
        repository=CanonicalRepository.FRAPPE,
        version="v15.103.1",
        commit="61ab7e2b2409b293ffd3c8f72d730fa89b201332",
        relative_path=relative_path,
        collected_at="2026-07-27T12:00:00+00:00",
    )


# -- _module_dotted_name -----------------------------------------------------------------------------


def test_module_dotted_name_for_a_regular_file() -> None:
    assert _module_dotted_name("frappe/model/document.py") == "frappe.model.document"


def test_module_dotted_name_for_an_init_file_is_the_package_itself() -> None:
    assert _module_dotted_name("frappe/utils/__init__.py") == "frappe.utils"


def test_module_dotted_name_for_a_top_level_file() -> None:
    assert _module_dotted_name("hooks.py") == "hooks"


# -- _qualified_symbol --------------------------------------------------------------------------------


def test_qualified_symbol_without_a_class() -> None:
    assert _qualified_symbol("apex_dashboard.api", None, "get_data") == "apex_dashboard.api.get_data"


def test_qualified_symbol_with_a_class() -> None:
    assert (
        _qualified_symbol("erpnext.accounts.doctype.customer.customer", "Customer", "validate")
        == "erpnext.accounts.doctype.customer.customer.Customer.validate"
    )


# -- _compute_evidence_id -----------------------------------------------------------------------------


def test_compute_evidence_id_is_deterministic_for_identical_inputs() -> None:
    first = _compute_evidence_id(
        CanonicalRepository.FRAPPE,
        "frappe/model/document.py",
        421,
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "frappe.model.document.Document.validate",
        "validate",
    )
    second = _compute_evidence_id(
        CanonicalRepository.FRAPPE,
        "frappe/model/document.py",
        421,
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "frappe.model.document.Document.validate",
        "validate",
    )
    assert first == second


def test_compute_evidence_id_changes_when_any_single_field_changes() -> None:
    base = _compute_evidence_id(
        CanonicalRepository.FRAPPE,
        "frappe/model/document.py",
        421,
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "frappe.model.document.Document.validate",
        "validate",
    )
    different_line = _compute_evidence_id(
        CanonicalRepository.FRAPPE,
        "frappe/model/document.py",
        422,
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "frappe.model.document.Document.validate",
        "validate",
    )
    different_repository = _compute_evidence_id(
        CanonicalRepository.ERPNEXT,
        "frappe/model/document.py",
        421,
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "frappe.model.document.Document.validate",
        "validate",
    )
    assert base != different_line
    assert base != different_repository


def test_compute_evidence_id_is_a_sha256_hex_digest() -> None:
    evidence_id = _compute_evidence_id(
        CanonicalRepository.FRAPPE,
        "frappe/model/document.py",
        421,
        EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
        "frappe.model.document.Document.validate",
        "validate",
    )
    assert len(evidence_id) == 64
    assert all(character in "0123456789abcdef" for character in evidence_id)


# -- _dotted_name / _decorator_dotted_name ----------------------------------------------------------


def test_dotted_name_resolves_a_bare_name() -> None:
    tree = ast.parse("whitelist", mode="eval")
    assert _dotted_name(tree.body) == "whitelist"


def test_dotted_name_resolves_an_attribute_chain() -> None:
    tree = ast.parse("frappe.whitelist", mode="eval")
    assert _dotted_name(tree.body) == "frappe.whitelist"


def test_dotted_name_returns_none_for_an_unresolvable_expression() -> None:
    tree = ast.parse("registry[0]", mode="eval")
    assert _dotted_name(tree.body) is None


def test_dotted_name_returns_none_when_an_attribute_chain_has_an_unresolvable_base() -> None:
    # registry[0].whitelist -- an Attribute whose own .value is itself
    # unresolvable (a Subscript), not just a top-level unresolvable node.
    tree = ast.parse("registry[0].whitelist", mode="eval")
    assert _dotted_name(tree.body) is None


def test_decorator_dotted_name_unwraps_a_call() -> None:
    tree = ast.parse("frappe.whitelist()", mode="eval")
    assert _decorator_dotted_name(tree.body) == "frappe.whitelist"


def test_decorator_dotted_name_handles_a_bare_decorator_with_no_call() -> None:
    tree = ast.parse("frappe.whitelist", mode="eval")
    assert _decorator_dotted_name(tree.body) == "frappe.whitelist"


# -- _is_whitelist_decorator -------------------------------------------------------------------------


def test_is_whitelist_decorator_true_for_attribute_call() -> None:
    tree = ast.parse("frappe.whitelist()", mode="eval")
    assert _is_whitelist_decorator(tree.body) is True


def test_is_whitelist_decorator_true_for_bare_name() -> None:
    tree = ast.parse("whitelist", mode="eval")
    assert _is_whitelist_decorator(tree.body) is True


def test_is_whitelist_decorator_false_for_an_unrelated_decorator() -> None:
    tree = ast.parse("frappe.only_for('System Manager')", mode="eval")
    assert _is_whitelist_decorator(tree.body) is False


def test_is_whitelist_decorator_false_for_a_shape_that_is_neither_attribute_nor_name() -> None:
    tree = ast.parse("registry[0]()", mode="eval")
    assert _is_whitelist_decorator(tree.body) is False


# -- _class_membership --------------------------------------------------------------------------------


def test_class_membership_maps_direct_methods_only() -> None:
    tree = ast.parse(
        "class Customer:\n    def validate(self):\n        pass\n\ndef module_level_function():\n    pass\n"
    )
    membership = _class_membership(tree)
    class_node = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    method_node = next(
        node for node in class_node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    module_function_node = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "module_level_function"
    )
    assert membership[id(method_node)] == "Customer"
    assert id(module_function_node) not in membership


# -- collect_controller_lifecycle_hook_evidence -------------------------------------------------------


def test_collect_lifecycle_hook_evidence_finds_every_recognized_hook() -> None:
    source = (
        "class Customer:\n"
        "    def validate(self):\n"
        "        pass\n"
        "\n"
        "    def on_submit(self):\n"
        "        pass\n"
        "\n"
        "    def some_other_method(self):\n"
        "        pass\n"
    )
    tree = ast.parse(source, filename="erpnext/accounts/doctype/customer/customer.py")
    context = _context("erpnext/accounts/doctype/customer/customer.py")

    evidence = collect_controller_lifecycle_hook_evidence(tree, context)

    subjects = {record.subject for record in evidence}
    assert subjects == {"validate", "on_submit"}
    assert len(evidence) == 2
    for record in evidence:
        assert record.category == EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK
        assert record.collector == CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR
        assert record.symbol.startswith("erpnext.accounts.doctype.customer.customer.Customer.")


def test_collect_lifecycle_hook_evidence_ignores_a_non_function_class_body_statement() -> None:
    # A class attribute assignment sits directly in the class body
    # alongside methods -- must not be mistaken for a hook method.
    source = "class Customer:\n    some_attribute = 1\n\n    def validate(self):\n        pass\n"
    tree = ast.parse(source)
    context = _context()

    evidence = collect_controller_lifecycle_hook_evidence(tree, context)

    assert [record.subject for record in evidence] == ["validate"]


def test_collect_lifecycle_hook_evidence_ignores_a_module_level_function_named_validate() -> None:
    source = "def validate():\n    pass\n"
    tree = ast.parse(source)
    context = _context()

    evidence = collect_controller_lifecycle_hook_evidence(tree, context)

    assert evidence == ()


def test_collect_lifecycle_hook_evidence_distinguishes_two_classes_in_the_same_file() -> None:
    source = (
        "class Customer:\n"
        "    def validate(self):\n"
        "        pass\n"
        "\n"
        "class Supplier:\n"
        "    def validate(self):\n"
        "        pass\n"
    )
    tree = ast.parse(source)
    context = _context()

    evidence = collect_controller_lifecycle_hook_evidence(tree, context)

    symbols = {record.symbol for record in evidence}
    assert symbols == {"frappe.model.document.Customer.validate", "frappe.model.document.Supplier.validate"}
    assert evidence[0].evidence_id != evidence[1].evidence_id


def test_collect_lifecycle_hook_evidence_is_deterministic_across_repeated_calls() -> None:
    source = "class Customer:\n    def validate(self):\n        pass\n"
    tree = ast.parse(source)
    context = _context()

    first = collect_controller_lifecycle_hook_evidence(tree, context)
    second = collect_controller_lifecycle_hook_evidence(tree, context)

    assert first == second


# -- collect_whitelisted_api_decoration_evidence ------------------------------------------------------


def test_collect_decoration_evidence_finds_a_single_decorator() -> None:
    source = "@frappe.whitelist()\ndef get_data():\n    pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert len(evidence) == 1
    assert evidence[0].subject == "frappe.whitelist"
    assert evidence[0].symbol == "apex_dashboard.api.get_data"
    assert evidence[0].category == EvidenceCategory.WHITELISTED_API_DECORATION
    assert evidence[0].collector == CollectorName.WHITELISTED_API_DECORATION_COLLECTOR


def test_collect_decoration_evidence_emits_one_atomic_record_per_decorator() -> None:
    # The exact case the atomic-evidence principle exists for: a function
    # carrying two decorators must produce two independent records, never
    # one bundling both -- co-occurrence is Pattern Aggregation's job.
    source = "@frappe.whitelist()\n@frappe.only_for('System Manager')\ndef get_data():\n    pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert len(evidence) == 2
    subjects = {record.subject for record in evidence}
    assert subjects == {"frappe.whitelist", "frappe.only_for"}
    symbols = {record.symbol for record in evidence}
    assert symbols == {"apex_dashboard.api.get_data"}
    # Atomic: each decorator got its own evidence_id, not a shared one.
    assert evidence[0].evidence_id != evidence[1].evidence_id


def test_collect_decoration_evidence_includes_the_class_name_for_a_method() -> None:
    source = "class Api:\n    @frappe.whitelist()\n    def get_data(self):\n        pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert evidence[0].symbol == "apex_dashboard.api.Api.get_data"


def test_collect_decoration_evidence_detects_a_bare_whitelist_name() -> None:
    source = "from frappe import whitelist\n\n@whitelist\ndef get_data():\n    pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert len(evidence) == 1
    assert evidence[0].subject == "whitelist"


def test_collect_decoration_evidence_ignores_a_function_with_no_whitelist_decorator() -> None:
    source = "@frappe.only_for('System Manager')\ndef get_data():\n    pass\n"
    tree = ast.parse(source)
    context = _context()

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert evidence == ()


def test_collect_decoration_evidence_skips_an_unresolvable_decorator_without_crashing() -> None:
    # A whitelisted function also carrying a decorator this collector
    # cannot resolve to a dotted name (e.g. a subscript expression) --
    # the resolvable decorator is still emitted, the unresolvable one is
    # silently skipped rather than fabricating a subject for it.
    source = "@frappe.whitelist()\n@registry[0]\ndef get_data():\n    pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert len(evidence) == 1
    assert evidence[0].subject == "frappe.whitelist"


def test_collect_decoration_evidence_detects_an_async_function() -> None:
    source = "@frappe.whitelist()\nasync def get_data():\n    pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    evidence = collect_whitelisted_api_decoration_evidence(tree, context)

    assert len(evidence) == 1
    assert evidence[0].symbol == "apex_dashboard.api.get_data"


def test_collect_decoration_evidence_is_deterministic_across_repeated_calls() -> None:
    source = "@frappe.whitelist()\n@frappe.only_for('System Manager')\ndef get_data():\n    pass\n"
    tree = ast.parse(source, filename="apex_dashboard/api.py")
    context = _context("apex_dashboard/api.py")

    first = collect_whitelisted_api_decoration_evidence(tree, context)
    second = collect_whitelisted_api_decoration_evidence(tree, context)

    assert first == second
