# R004: Fixture & Metadata Integrity

## Principle
All custom metadata must be traceable, scoped, and reversible through its owning app:
1. Every `Custom Field` created programmatically must carry an explicit `"module"` tag pointing to the owning custom app.
2. Standard DocTypes (`{"dt": "DocType", ...}`) must **never** be exported as fixtures — behavioral changes to a standard DocType go through `Property Setter` fixtures only.
3. Deleting a fixture-declared field/setter means editing the app's fixture JSON file itself, not just the database record.

## Architectural Impact
These three failures compound into real production incidents, not theoretical risk:
- A `create_custom_fields()` call without a `module` key leaves orphaned fields behind after app uninstall — they were never actually owned by anything, so nothing cleans them up.
- Exporting a standard DocType as a fixture throws `CannotCreateStandardDoctypeError` the moment that fixture is restored on a fresh/production site — it's not a warning, it's a hard install blocker.
- Deleting a fixture-declared field from the database alone (without touching the JSON) means the next `bench migrate` re-reads the fixture file and **resurrects the field**, silently undoing the deletion.

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

## Risk Level
**Critical**
