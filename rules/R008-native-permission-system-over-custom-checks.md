# R008: Native Permission System Over Custom Permission Code

## Principle
Access control — including row-level ("see only your own records") security — must be built with Frappe's own **Role Permission Manager** and **User Permission** doctype, not with hand-written `if user == doc.owner` style checks scattered through `validate`/`has_permission` hooks. Roles are assigned and adjusted through the UI/fixtures, never hard-coded into application code.

## Architectural Impact
Custom permission-check code duplicates a system Frappe already solves generically, correctly, and consistently across every list view, report, API call, and desk form. It also silently diverges from what the UI shows an administrator ("who can see this?" becomes unanswerable by looking at Role Permission Manager alone, since some of the real rule is buried in Python). The Commission Manager architecture deliberately chose native `User Permission` records (each Commission Agent linked to a `user`, constrained via User Permissions) over a custom row-level filter, specifically so visibility rules stay inspectable and editable by an admin through the standard Role/User Permission screens — not something only a developer reading source code can determine.

## Bad Pattern
```python
# validate() or a custom permission_query_conditions function reinventing row-level security
def has_permission(doc, user):
    agent = frappe.db.get_value("Commission Agent", {"user": user}, "name")
    return doc.commission_agent == agent  # bespoke, invisible to Role Permission Manager
```

## Good Pattern
Link each `Commission Agent` to a `user`, then create a **User Permission** record restricting that user to their own `Commission Agent` value — Frappe's built-in permission engine then automatically applies that restriction everywhere (list views, reports, API), with zero custom permission code, and it's visible/editable by an admin in the standard User Permissions screen.

## Risk Level
**Medium**
