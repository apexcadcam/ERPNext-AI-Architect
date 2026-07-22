# R005: Idempotent, Upgrade-Safe Deployment

## Status
Stable

## Risk Level
**High**

## Rule
Installation and permission logic must survive partial failure and repeated runs without corrupting state:
1. `after_install` (and any migration hook) must wrap **each provisioning step** in its own `try/except`, never one monolithic uncaught block.
2. `hooks.py` must explicitly declare `required_apps` for any cross-app dependency.
3. Reports and permission sets must be **UI-managed**: ship with `is_standard: "No"` and an empty `roles` list, import once via `after_install`, then leave role assignment entirely to the site administrator through the UI.

## Rationale
A single unhandled step inside installation or migration can abort the entire process with no diagnosable trace. A missing cross-app dependency declaration can pass in a development environment where the dependency happens to already be present, then hard-fail on a clean production site. Hard-coding roles into a Report's JSON means every fixture sync overwrites whatever roles an administrator actually assigned through the UI, silently reverting real permission changes.

## Scope
Applies to any `after_install`/migration hook, any cross-app dependency, and any Report or permission set shipped by a custom app.

## Bad Pattern
```python
def after_install():
    create_custom_fields(...)
    import_reports(...)
    setup_workflows(...)
    # any single failure here aborts everything, with no indication which step failed
```
```json
// report JSON
{"is_standard": "Yes", "roles": [{"role": "Sales Manager"}]}
```

## Good Pattern
```python
def after_install():
    for step in (create_custom_fields, import_reports, setup_workflows):
        try:
            step()
        except Exception:
            frappe.log_error(title=f"after_install failed: {step.__name__}")
```
```python
# hooks.py
required_apps = ["frappe", "erpnext"]
```
```json
// report JSON — roles assigned once via after_install, then owned by the UI
{"is_standard": "No", "roles": []}
```

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R004 — Fixture & Metadata Integrity](R004-fixture-and-metadata-integrity.md); [R006 — Full Reproducibility](R006-full-reproducibility-fixtures-and-patches.md)

## Related Anti-Patterns
None yet.
