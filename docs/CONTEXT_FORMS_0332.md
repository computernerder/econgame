# Relevant fields and choices — 0.33.2

Service requests now start with the service and receiving account. Legal matters appear only for legal work. Routine accounting and legal templates do not ask for a target. Training and onboarding offer active employees of the receiving business; collection work offers that account's eligible overdue balances and claims. Previously negotiated offers and invoices with recovery in progress are excluded from the corresponding choices.

Outsourced work hides and disables the internal provider field. Internal and mixed delivery offer configured departments for the selected service and receiving business's county. A department can still have insufficient qualified staff capacity: the form explains that actual staff time and other queued work determine completion. No department, employee time, quote, or financial result is fabricated by these UI changes.

The same dependency handling covers recruiting roles, candidate assessments, onboarding, IT installation/support prerequisites, property transaction review and consent, and in-house agent requests. Property conversion use is omitted from repair submissions. Tenant maintenance requests follow the selected property. Empty required selections show an explanation and disable Review; missing internal service departments include a setup link.

Read-only field metadata supplies both initial HTML and browser behavior. Hidden controls are disabled, so changing tasks does not submit unrelated values. Live account balances follow rebuilt choices. Existing fields and descriptions are retained on other forms. Fixed invoice-specific collection shortcuts retain their exact targets.

The simulation also normalizes outsourced providers and ignores irrelevant legal/target values from old generic service forms. Employee development validates that the target is an active employee of the receiving business before any reserve is paid. Actual service effort, costs, qualification checks, approval rules, queues, and delivery outcomes remain in the existing simulation.

Validation actually executed:

- 150 tests passed across context forms, department UI, UI workflows, service projects, commercial contracts, property scale, property work context, repair-all, HR hiring costs, customer collections, manager routines, and funding balances.
- Nine new tests cover initial hidden/disabled fields, read-only views, account-specific balances and employees, matching departments/counties, industry roles and IT prerequisites, stale-value cleanup, invalid training rejection before spending, and property-dependent controls.
- JavaScript syntax checks passed for `context_forms.js` and `funding.js`.
- An independent browser campaign exercised outside accounting, internal accounting, unavailable internal legal work with a setup link, legal collection targeting, and switching back to accounting. The confirmed accounting request reserved $720 for eight hours. Reloading its saved data and auditing the ledger confirmed an outside accounting task with no stale legal matter or target.
- The full repository suite was not run. Existing FastAPI/Starlette dependency deprecation warnings remain.

Limits: this pass covers the related service and property-work forms, not every input in the game. Eligibility can change after the screen loads; the existing preview and confirmation validate current simulation state. Agent delivery still depends on the selected property's county and real qualifications, and department staffing is not guaranteed by configuration alone.

Restart the launcher to load 0.33.2. Existing game saves need no migration. Next usability pass: apply these dependencies to any remaining mixed-purpose financial, staffing, and property forms identified during play.
