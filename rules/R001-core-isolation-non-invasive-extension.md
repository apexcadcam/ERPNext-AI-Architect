# R001: Core Isolation & Non-Invasive Extension

## Status
Stable

## Risk Level
**Critical**

## Rule
Never modify a file inside `apps/frappe` or `apps/erpnext` (or any other vendor app). Every customization — field, validation, UI change, business rule — must live inside our own custom app and be applied through Frappe's official extension points: **Custom Field, Property Setter, Client Script, Server Script, hooks.py** (`doc_events`, `override_doctype_class`, `override_whitelisted_methods`), or a genuinely new Custom DocType.

## Rationale
`bench update` overwrites core app files on every release. A direct edit to core is not a customization, it's a ticking time bomb: it disappears (or worse, half-merges and corrupts) on the next update, with no error message pointing at the cause. It also means real customization must be fully discoverable in a `git diff` of one custom app — if someone has to `grep` through a vendor app to find out why a doctype behaves oddly, isolation has already failed.

## Scope
Applies whenever any change is proposed to a DocType, field, or behavior that lives inside a vendor app (`frappe`, `erpnext`, or any other installed vendor app).

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

## Exceptions
None.

## Evidence
**Origin:** Legacy Production Experience
**Additional:** None

## Related Rules
[R002 — Native-First Discovery](R002-native-first-discovery.md); [R003 — Low-Code / Configuration Over Code](R003-low-code-configuration-over-code.md)

## Related Anti-Patterns
None yet.
