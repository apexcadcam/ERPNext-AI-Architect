# R008: Native Permission System Over Custom Permission Code

## Status
Stable

## Risk Level
**Medium**

## Rule
Access control — including row-level ("see only your own records") security — must be built with Frappe's own **Role Permission Manager** and **User Permission** doctype, not with hand-written `if user == doc.owner` style checks scattered through `validate`/`has_permission` hooks. Roles are assigned and adjusted through the UI/fixtures, never hard-coded into application code.

## Rationale
Custom permission-check code duplicates a system Frappe already solves generically, correctly, and consistently across every list view, report, API call, and desk form. It also silently diverges from what the UI shows an administrator — "who can see this?" becomes unanswerable by looking at Role Permission Manager alone, since part of the real rule is buried in Python instead of visible in a standard permissions screen.

## Scope
Applies whenever access control — including row-level visibility — is being implemented for any DocType in a custom app.

## Bad Pattern
```python
# validate() or a custom permission_query_conditions function reinventing row-level security
def has_permission(doc, user):
    agent = frappe.db.get_value("Commission Agent", {"user": user}, "name")
    return doc.commission_agent == agent  # bespoke, invisible to Role Permission Manager
```

## Good Pattern
Link the relevant record to a `user`, then create a **User Permission** record restricting that user to their own linked value — Frappe's built-in permission engine then automatically applies that restriction everywhere (list views, reports, API), with zero custom permission code, and it's visible/editable by an admin in the standard User Permissions screen.

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R001 — Core Isolation & Non-Invasive Extension](R001-core-isolation-non-invasive-extension.md); [R002 — Native-First Discovery](R002-native-first-discovery.md)

## Related Anti-Patterns
None yet.
