# Usability and workflow update — 0.27.0

This update addresses the review of version 0.26.3 using an isolated copy of the player's active campaign. It preserves economic actions, payroll, authority enforcement, stable identities and save format. No live campaign is edited during installation.

## Implemented

- Business and Team pages have an immediately visible role picker, **Find candidates**, **Manage vacancies** and **Edit hiring policy and staff target**. The calculated staffing guide explains its distinction from the editable hiring target. HR, IT and HVAC use consistent display labels.
- Management opens with leaders and policy summaries. Each business links directly to its staffing policy and delegated limits. Detailed leadership activity remains available below and through a direct Activity shortcut; long tables can scroll horizontally.
- Employee pages show actual employer, primary supervisor and current leadership duties near the name, with jumps to time off, pay and career history. This reorders existing records rather than creating new reporting relationships.
- Home-office services starts with pending work and department capacity, with direct request/configure/outsource/priority actions. Pending tasks precede completed work. Provider, recipient, employee names and capacity units are visible. Company finances/setup and completed work products remain expandable. The screen explicitly identifies its group-wide queue.
- Property repair and building links carry the selected property; system-specific links also carry the system. Focused forms open near the top. The selected property is fixed in that focused form, with its owner/paying account and cash shown. The general workbench remains available for choosing another property. Unknown or incompatible destinations show a status explanation and do not focus a different asset.
- Navigation to a control inside a collapsed panel opens the control and its enclosing panels. Form preview failures appear beside the submitted form and preserve entered values. Recovery links can return to the exact property/system or hiring role.
- Completed development no longer displays the original empty-land description. A read-only description is derived when the original stock land text is stale; custom property descriptions and names are retained. Industry specialization labels are readable.
- Collection inbox cards identify the invoice and explain default versus overdue status, including why a future-dated invoice can need review. Stable inbox IDs and action links remain intact.
- Existing campaign Home shows decisions, real business balances/results and owned property before growth suggestions. New campaigns retain their introductory view. Per-business results are explicitly distinguished from consolidated profit.
- Account balances are labeled **Cash on hand**, including funding widgets. Existing authority forecasts still show cash after known commitments separately. The sticky balance remains visible.
- Business navigation includes Services. Global shortcuts are grouped under **More management tools**, and Home office has its own sidebar destination. No business-section tab silently switches into a different account.

## Validation

Full regression suite: **509 passed**, two existing dependency deprecation warnings, 309.52 seconds. Eleven new workflow tests cover property/owner/system selection, incompatible destinations, recovery context, hiring and policy access, management ordering, service focus, employee context, current development descriptions, established-campaign Home, invoice identity and role-specific recovery. The existing home-office test now verifies default collapsed setup and explicit focused setup.

All **31** read-only HTTP page checks returned 200 on the copied active campaign, including focused repair and department routes. The world was unchanged and its journal audit passed. Python source parsing also passed.

Browser checks at 1041 × 1216 confirmed:

- The Northbank property repair shortcut opens Northbank, rather than the subsidiary's Willow Industrial Yard.
- The management leader directory begins near 688 pixels instead of 4,889; its staffing-policy link opens the correct panel.
- The home-office queue begins near 653 pixels instead of 3,798, and direct department setup keeps Group Shared Services as provider.
- Team role selection reaches HVAC candidates. An intentionally unattractive offer displays an inline rejection and retains the entered salary; no hire or payment was committed.
- The established campaign dashboard uses actual business/property records.

All 31 final focused regression checks passed after the final label adjustments; the installation record records source hashes and backup location. Browser screenshots and page measurements are QA evidence, not hard-coded dashboard values.

## Limits and follow-up

This is a focused workflow improvement, not a complete visual redesign or full accessibility/mobile audit. Long audit tables still use horizontal scrolling; service queues display up to 100 records. Core staffing recommendations remain calculated, and specialist availability still follows industry rules. Setup and detailed records remain in expandable panels. A later increment can add department-specific dashboards, fuller queue pagination, saved filters and a responsive/accessibility audit.

Restart the game after installation to load both the new templates and simulation-facing view code. Refreshing an old server session is insufficient. Existing saved games require no migration.
