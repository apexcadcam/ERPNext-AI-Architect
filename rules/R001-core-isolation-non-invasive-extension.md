# R001: Core Isolation & Non-Invasive Extension

## Principle
Never modify a file inside `apps/frappe` or `apps/erpnext` (or any other vendor app). Every customization — field, validation, UI change, business rule — must live inside our own custom app and be applied through Frappe's official extension points: **Custom Field, Property Setter, Client Script, Server Script, hooks.py (`doc_events`, `override_doctype_class`, `override_whitelisted_methods`)**, or a genuinely new Custom DocType.

## Architectural Impact
`bench update` overwrites core app files on every release. A direct edit to core is not a customization, it's a ticking time bomb: it disappears (or worse, half-merges and corrupts) on the next update, with no error message pointing at the cause. It also means 100% of our real customization must be discoverable in a `git diff` of one custom app — if someone has to `grep` through `apps/erpnext` to find out why a doctype behaves oddly, isolation has already failed.

## Bad Pattern
```python
# apps/erpnext/erpnext/crm/doctype/contact/contact.py  (hand-edited)
def validate(self):
    if not self.mobile_no:
        frappe.throw("Mobile number required")  # <-- edited core file directly
```

## Good Pattern
```python
# apps/apex_customization/apex_customization/hooks.py
doc_events = {
    "Contact": {
        "validate": "apex_customization.overrides.contact.validate_mobile_required"
    }
}
```
Field-level and behavioral changes to standard doctypes go through Custom Field / Property Setter fixtures in the custom app — never through edits to the shipped doctype files.

## Risk Level
**Critical**
