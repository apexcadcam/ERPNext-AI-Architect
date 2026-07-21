# R002: Native-First Discovery (Research Before You Build)

## Principle
Before designing any new field, child table, or DocType, you must first **prove that Frappe/ERPNext core does not already solve the problem**. Exhaust the standard doctypes, the "Address & Contact" pattern, existing child tables, and standard reports/dashboards before writing a single line of a custom solution. If a satisfying native mechanism exists, use it — even if it's not a perfect fit — rather than building a parallel structure.

## Architectural Impact
Skipping discovery produces duplicate, competing data models that fragment the same real-world concept across multiple places. This is not hypothetical: we built custom `phone_no_1` / `phone_no_2` fields (and a "Smart Contact Details" layer on top) on CRM records to store multiple phone numbers — only to later discover that Frappe's native **Contact** doctype already ships a **Contact Phone child table**, already wired into the standard "Address & Contact" section that Customer and CRM doctypes expose, and already exports correctly wherever Contacts are consumed (communication, calendar, integrations). We solved a problem that didn't exist, at the cost of a parallel, disconnected data model that native tooling doesn't know about. Every custom structure built without this check is future migration debt and a fork of ERPNext's own data model.

## Bad Pattern
Adding `phone_no_1`, `phone_no_2`, `phone_no_3` custom fields directly to CRM Lead/Customer to capture multiple contact numbers, invented without checking what already renders on the "Address & Contact" section.

## Good Pattern
Use the native `Contact` doctype (linked via Dynamic Link to the parent record) and its built-in `Contact Phone` child table, surfaced through the standard "Address & Contact" widget already present on Customer, Lead, and other party doctypes. If the native model is missing one attribute (e.g. a "primary" flag), extend it with a Custom Field on the *existing* child table — don't rebuild the whole structure from scratch.

## Risk Level
**High**
