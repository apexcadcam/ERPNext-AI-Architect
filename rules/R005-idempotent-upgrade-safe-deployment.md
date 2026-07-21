# R005: Idempotent, Upgrade-Safe Deployment

## Principle
Installation and permission logic must survive partial failure and repeated runs without corrupting state:
1. `after_install` (and any migration hook) must wrap **each provisioning step** in its own `try/except`, never one monolithic uncaught block.
2. `hooks.py` must explicitly declare `required_apps` for any cross-app dependency.
3. Reports and permission sets must be **UI-managed**: ship with `is_standard: "No"` and an empty `roles` list, import once via `after_install`, then leave role assignment entirely to the site administrator through the UI.

## Architectural Impact
On Frappe Cloud specifically, a single unhandled exception inside `after_install` aborts the entire install — and the deploy sandbox often surfaces this as an **empty, silent failure log**, making it nearly impossible to diagnose after the fact. A missing `required_apps` entry means the app installs successfully in dev (where the dependency happens to already be present) and then hard-fails on a clean production site. Hard-coding `roles` into a Report's JSON means every fixture sync **overwrites whatever roles the customer actually assigned in the UI**, silently reverting their permission changes on the next deploy.

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

## Risk Level
**High**
