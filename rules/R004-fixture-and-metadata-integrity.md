# R004: Fixture & Metadata Integrity

## Status
Stable

## Risk Level
**Critical**

## Rule
All custom metadata must be traceable, scoped, and reversible through its owning app:
1. Every `Custom Field` created programmatically must carry an explicit `"module"` tag pointing to the owning custom app.
2. Standard DocTypes (`{"dt": "DocType", ...}`) must **never** be exported as fixtures — behavioral changes to a standard DocType go through `Property Setter` fixtures only.
3. Deleting a fixture-declared field/setter means editing the app's fixture JSON file itself, not just the database record.

## Rationale
Untracked or malformed fixture/metadata changes become invisible, unreversible technical debt: a field with no module tag is never actually owned by anything and is left orphaned on uninstall, a standard DocType exported as a fixture hard-blocks installation on a fresh site, and a field deleted only from the database gets silently resurrected the next time fixtures are migrated.

## Scope
Applies whenever a Custom Field, Property Setter, or other fixture-tracked metadata is created, modified, or removed in a custom app.

## Bad Pattern
```python
create_custom_fields({
    "Customer": [{"fieldname": "loyalty_tier", "fieldtype": "Select", ...}]
    # no "module" key — orphaned on uninstall
})
```
```json
// fixtures list in hooks.py
"fixtures": [{"dt": "DocType", "filters": [["name", "=", "Customer"]]}]
```

## Good Pattern
```python
create_custom_fields({
    "Customer": [{"fieldname": "loyalty_tier", "fieldtype": "Select",
                  "module": "Apex Customization", ...}]
})
```
Behavioral tweaks to standard doctypes go through `Property Setter` fixtures scoped by module filter. Any field removal is done by editing and re-exporting the app's `custom_field.json` (or equivalent fixture file), then running `bench migrate` — never a bare database delete.

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R005 — Idempotent, Upgrade-Safe Deployment](R005-idempotent-upgrade-safe-deployment.md); [R006 — Full Reproducibility](R006-full-reproducibility-fixtures-and-patches.md)

## Related Anti-Patterns
None yet.
