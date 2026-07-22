# R006: Full Reproducibility (Fixtures + Patches, No Manual Steps)

## Status
Stable

## Risk Level
**Critical**

## Rule
An app's entire state — UI configuration AND data-affecting changes — must be reconstructable from git alone. Every Custom Field/Property Setter/Workflow/Workspace created through the UI must be exported as a fixture before commit. Every change that touches existing *data* (not just metadata) must ship as an idempotent Patch (`patches.txt`, using `db_update()`), never as a one-off `bench console` script or a manual DB edit. The test of correctness: delete the site, run `bench get-app` + `bench install-app` + `bench migrate` from a clean database, and the system must behave **identically** to before.

## Rationale
Manual UI configuration and ad-hoc console scripts are invisible to git — they live only in one database, on one server, in one person's memory. The moment that site is rebuilt, restored from an older backup, or handed to a new host, that undocumented state is gone and nothing in the repository can reproduce it. The same failure mode applies to any change applied "just this once" through the UI or a console session instead of through fixtures/patches: it works until the next real deploy, then quietly doesn't exist.

## Scope
Applies to any UI-driven configuration change or any change touching existing data, and to any app/process deployment step.

## Bad Pattern
Adding a Custom Field through the desk UI and never running `bench export-fixtures`; backfilling/correcting live data with a throwaway `bench console` snippet that's never turned into a patch; assuming a `kill -HUP <gunicorn_master>` reloads newly installed app code (it only respawns workers from the *already-loaded* code — new Python modules are never re-imported).

## Good Pattern
```python
# patches.txt
myapp.patches.v1_0.backfill_loyalty_tier

# myapp/patches/v1_0/backfill_loyalty_tier.py
import frappe

def execute():
    for row in frappe.get_all("Customer", fields=["name"]):
        doc = frappe.get_doc("Customer", row.name)
        if not doc.get("loyalty_tier"):
            doc.loyalty_tier = "Standard"
            doc.db_update()
```
Every UI-created Custom Field/Property Setter is exported to the fixture JSON in the same commit that introduces it. After any change to what Python modules are importable (new/removed app), the gunicorn master process itself is killed outright — not `SIGHUP`'d — so supervisord spawns a genuinely fresh master that re-imports current code.

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R004 — Fixture & Metadata Integrity](R004-fixture-and-metadata-integrity.md); [R005 — Idempotent, Upgrade-Safe Deployment](R005-idempotent-upgrade-safe-deployment.md)

## Related Anti-Patterns
None yet.
