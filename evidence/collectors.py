"""Evidence Extraction Engine's own collector logic.

Implements Evidence Extraction Engine Architecture Specification v1.1 §7
exactly: two deterministic, `ast`-based collectors, plus the internal
helpers for computing a fully module-qualified `symbol` and a
content-addressed `evidence_id`. Both collectors are pure, take no
dependency on anything outside the standard library's `ast` module plus
this package's own contracts, and emit **atomic** Evidence -- one record
per single observed fact (§3, §5). Neither collector aggregates,
compares, or scores anything; Pattern Aggregation is explicitly Sprint
21's own, later, separate stage.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from evidence.contract import (
    CanonicalRepository,
    CollectorName,
    Evidence,
    EvidenceCategory,
    EvidenceKind,
    Source,
)

#: §3.1's fixed, closed list of recognized Frappe `Document` lifecycle
#: hook names. A method named anything else is not evidence of a
#: lifecycle hook, no matter where it is defined.
_LIFECYCLE_HOOK_NAMES = frozenset(
    {
        "validate",
        "before_insert",
        "before_save",
        "after_insert",
        "on_update",
        "before_submit",
        "on_submit",
        "on_cancel",
        "on_trash",
        "after_delete",
        "on_update_after_submit",
    }
)


@dataclass(frozen=True)
class _FileContext:
    """Package-internal. The per-file provenance both collectors need to
    build a `Source` and a content-addressed `evidence_id` -- everything
    `Source` itself carries except `line`, which varies per emitted
    record within the same file.
    """

    repository: CanonicalRepository
    version: str
    commit: str
    relative_path: str
    collected_at: str


def _module_dotted_name(relative_path: str) -> str:
    """Converts a repository-relative file path into the Python dotted
    module name it represents -- `frappe/model/document.py` becomes
    `frappe.model.document`; `frappe/utils/__init__.py` becomes
    `frappe.utils` (a package's own `__init__.py` *is* the package, not a
    `.__init__` submodule of it).
    """

    parts = list(PurePosixPath(relative_path).parts)
    if parts and parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _qualified_symbol(module_name: str, class_name: str | None, function_name: str) -> str:
    """Builds the fully module-qualified `symbol` (spec §6.6) -- prevents
    the ambiguity a bare `Customer.validate` would carry when more than
    one same-named class exists across different modules.
    """

    if class_name is None:
        return f"{module_name}.{function_name}"
    return f"{module_name}.{class_name}.{function_name}"


def _compute_evidence_id(
    repository: CanonicalRepository,
    relative_path: str,
    line: int,
    category: EvidenceCategory,
    symbol: str,
    subject: str,
) -> str:
    """Content-addressed `evidence_id` (spec §6.6): a `sha256` digest of
    the fact's own defining fields. The same fact at the same commit
    always produces the same id, in any run -- never a UUID, which would
    make every run's output look "different" even when nothing changed.
    """

    payload = "|".join([repository.value, relative_path, str(line), category.value, symbol, subject])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_evidence(
    *,
    context: _FileContext,
    category: EvidenceCategory,
    symbol: str,
    subject: str,
    line: int,
    collector: CollectorName,
) -> Evidence:
    source = Source(
        repository=context.repository,
        version=context.version,
        commit=context.commit,
        relative_path=context.relative_path,
        line=line,
    )
    evidence_id = _compute_evidence_id(
        context.repository, context.relative_path, line, category, symbol, subject
    )
    return Evidence(
        evidence_id=evidence_id,
        kind=EvidenceKind.IMPLEMENTATION,
        category=category,
        symbol=symbol,
        subject=subject,
        source=source,
        collector=collector,
        collected_at=context.collected_at,
    )


def _class_membership(tree: ast.Module) -> dict[int, str]:
    """Maps `id(function_node) -> enclosing class name`, for every
    function defined directly in a class body -- one level, matching how
    Frappe DocType controllers and API modules are actually structured.
    A function nested inside another function, or inside a doubly-nested
    class, is deliberately not attributed to any class here.
    """

    membership: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    membership[id(child)] = node.name
    return membership


def _decorator_dotted_name(decorator: ast.expr) -> str | None:
    func = decorator.func if isinstance(decorator, ast.Call) else decorator
    return _dotted_name(func)


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _is_whitelist_decorator(decorator: ast.expr) -> bool:
    func = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(func, ast.Attribute):
        return func.attr == "whitelist"
    if isinstance(func, ast.Name):
        return func.id == "whitelist"
    return False


# -- Collector 1: Controller Lifecycle Hook Usage -------------------------------------------------------


def collect_controller_lifecycle_hook_evidence(
    tree: ast.Module, context: _FileContext
) -> tuple[Evidence, ...]:
    """§7's first collector. For every class definition whose methods
    include a recognized lifecycle hook name, emits one Evidence record
    per (class, hook) pair -- already atomic by construction, one hook
    per record, exactly as it was in Specification v1.0.
    """

    module_name = _module_dotted_name(context.relative_path)
    evidence: list[Evidence] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name not in _LIFECYCLE_HOOK_NAMES:
                continue
            symbol = _qualified_symbol(module_name, node.name, child.name)
            evidence.append(
                _build_evidence(
                    context=context,
                    category=EvidenceCategory.CONTROLLER_LIFECYCLE_HOOK,
                    symbol=symbol,
                    subject=child.name,
                    line=child.lineno,
                    collector=CollectorName.CONTROLLER_LIFECYCLE_HOOK_COLLECTOR,
                )
            )

    return tuple(evidence)


# -- Collector 2: Whitelisted API Decoration Pattern ----------------------------------------------------


def collect_whitelisted_api_decoration_evidence(
    tree: ast.Module, context: _FileContext
) -> tuple[Evidence, ...]:
    """§7's second collector. For every function carrying at least one
    decorator whose attribute chain ends in `whitelist`, emits **one
    Evidence record per individual decorator** present on that function --
    never a single record bundling the whole decorator set. Whether
    `whitelist` and, say, `only_for` tend to appear together is Pattern
    Aggregation's (Sprint 21's) own question to answer later, by grouping
    Evidence on shared `symbol` -- not something this collector infers.
    """

    module_name = _module_dotted_name(context.relative_path)
    class_membership = _class_membership(tree)
    evidence: list[Evidence] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(_is_whitelist_decorator(decorator) for decorator in node.decorator_list):
            continue

        class_name = class_membership.get(id(node))
        symbol = _qualified_symbol(module_name, class_name, node.name)

        for decorator in node.decorator_list:
            decorator_name = _decorator_dotted_name(decorator)
            if decorator_name is None:
                continue
            evidence.append(
                _build_evidence(
                    context=context,
                    category=EvidenceCategory.WHITELISTED_API_DECORATION,
                    symbol=symbol,
                    subject=decorator_name,
                    line=node.lineno,
                    collector=CollectorName.WHITELISTED_API_DECORATION_COLLECTOR,
                )
            )

    return tuple(evidence)
