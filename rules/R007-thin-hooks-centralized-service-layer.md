# R007: Thin Hooks, Centralized Service Layer

## Status
Stable

## Risk Level
**High**

## Rule
`hooks.py` and its `doc_events` targets are wiring, not logic. A hook function should be a 3-4 line call into a dedicated, testable service/engine module (e.g. `myapp/engine/commission_engine.py`, `myapp/services/`) — never the place where the actual calculation, validation, or side-effect logic lives. Real business logic belongs in plain functions/classes that can be unit-tested without triggering a document event at all, and must never manage its own database transaction (`frappe.db.commit()`) — that's the request lifecycle's job, not a hook's.

## Rationale
When logic lives directly inside scattered `doc_events` handlers across many small files, there is no single place to unit-test what a document event is supposed to do — it can only be integration-tested by actually submitting documents. Calling `frappe.db.commit()` inside a hook also forces a commit mid-request, splitting what should be one atomic operation into multiple, so a later failure in the same request leaves the database partially written with no way to roll back the earlier hook's effects.

## Scope
Applies whenever a `doc_events` hook (or other hook target) is being written in a custom app.

## Bad Pattern
```python
# hooks.py handler with logic embedded directly, plus a manual commit
def on_submit(doc, method):
    total = 0
    for item in doc.items:
        total += item.qty * item.rate * get_commission_rate(item.item_group)
    frappe.get_doc({"doctype": "Commission Assignment", ...}).insert()
    frappe.db.commit()  # anti-pattern: hooks must not manage their own transaction
```

## Good Pattern
```python
# hooks.py — thin, just wiring
doc_events = {
    "Sales Invoice": {"on_submit": "myapp.engine.commission_engine.on_invoice_submit"},
}

# myapp/engine/commission_engine.py — the real, testable logic
class CommissionEngine:
    @staticmethod
    def calculate_assignment(invoice):
        ...  # unit-testable without ever calling doc.submit()

def on_invoice_submit(doc, method):
    CommissionEngine.calculate_assignment(doc)
```

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R003 — Low-Code / Configuration Over Code](R003-low-code-configuration-over-code.md); [R009 — YAGNI](R009-yagni-no-speculative-infrastructure.md)

## Related Anti-Patterns
None yet.
