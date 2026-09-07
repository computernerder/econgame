# Manager-led routine operations — 0.29.0

Daily operating work now goes to an available local manager or property manager before an assigned director. Directors handle equipment growth, locations, financing and flip commitments, and can cover routine work when the business has no available local manager. An employee with active director/VP duties is not treated as a separate store manager. Explicitly assigned employee supervisors remain responsible for leave reviews, including across companies.

## Routine care and collections

Management overview and Property services expose a **Routine care and collections** policy for each business. It controls invoice follow-up, agency use, property care, renewals, provider preference, monthly commitments, condition threshold and plan length. Existing manager delegation must be enabled; this update does not grant broader permissions or change saved limits.

- Managers send free reminders for overdue customer invoices, propose installments if reminders fail, and can use the existing contingency agency after both fail. The full possible agency fee counts against authority, while cash fees remain proportional to actual collections. Existing paid, overdue and defaulted invoices are preserved.
- Managers book cleaning and landscaping when care falls below the selected threshold (default 60), and renew completed plans at their existing visit interval. Security renews an already selected plan; initial security coverage remains a player choice. Cancelling a plan stops that service's automatic renewal until a later plan is manually booked.
- Qualified owned providers are preferred if an available crew, current licenses, equipment, supply cash and sufficient visit/travel time are present. A crew with another active property-service plan is conservatively treated as booked; otherwise outside specialists are used. Existing service simulation consumes labor, supplies and time and reduces external selling capacity.
- New plans default to four visits. The whole prepaid plan must fit the routine monthly budget, legacy purchase ceiling, authority contract and cash forecast. Plans are not shortened to bypass a limit. The default monthly routine budget is four times the existing purchase ceiling. Explicit parent authority still applies.
- Routine administrative capacity is limited to at most 120 minutes per manager per day or 60 minutes for a covering director, capped by the employee's scheduled day and shared across covered businesses. A booking uses 20 minutes; a collection action uses 10. This is a high-level administrative allowance, not a new payroll charge.

Each action records the actual employee, role, business, outcome, cash cost and full authority commitment in Leadership activity. If a manager needs more authority, an exception reaches the decision inbox; an available higher-budget director does not silently execute the same store task. Existing open requests remain for player review. Successful same-day invoice follow-up suppresses only the matching payment interruption, leaving unrelated safety and financial stops intact.

## Compatibility and limits

No headquarters or extra management layer is required. Personal properties remain owner-managed. Existing disabled delegation and explicitly disabled property automation are respected. Repairs, leasing, shared-service work, hiring and strategic growth retain their existing individual policy controls. Legal engagement, exhausted recovery choices and write-offs remain player decisions. This release does not retune customer reliability or grant new loans.

The saved hierarchy, employee identities, payroll accounts, ownership and historical action attribution are preserved. New optional policy data lives in the existing saved authority structure. Internal rent and service accounting use the existing reconciliation rules. New UI amounts use whole dollars; exact cents remain in the ledger.

Provider selection is deliberately conservative rather than an optimized crew dispatch schedule. Director strategy still depends on the business's existing enabled operating policies. Absence cover is subject to the director's own workload, authority and reserves. A manager can perform permitted strategic actions when there is no available director.

## Validation

- Final complete suite: **547 passed**, 2 pre-existing dependency deprecation warnings (315.53 seconds), using the project's Python with `-X utf8 -B -m pytest -q -p no:cacheprovider`.
- Focused final regression run: **101 passed**, covering manager routines, employee leave/reporting, property services, authority, leadership activity and UI workflows. Earlier focused run: 90 passed.
- Nineteen new cases cover manager/director routing, absence cover, explicit disabled delegation, actual actor attribution, full agency commitments, invoice event handling, monthly limits, security renewal/cancellation, personal-property exclusion, care opt-out, parent prohibitions, finite admin capacity, owned-provider qualifications/availability/queue limits, rendering without mutation, daily-step equivalence, save/load and ledger audit.
- The first full run found one leave-review regression (545 passed, 1 failed). Explicit cross-company supervisors were restored; the unchanged regression and the full suite then passed. The older property-care booking branch was removed so it cannot override the new opt-out.

A read-only SQLite backup of the active campaign was advanced seven individual days, from 2026-04-27 to 2026-05-04. Its ledger audit passed. Eight new completed actions were recorded: seven by the local trades manager, including an owned-provider cleaning plan and customer follow-up, and one recruitment action by the home-office director where there was no separate local manager. An over-limit grounds renewal became a manager-attributed approval request. The original campaign was not advanced or edited.

Browser QA on that separate test save checked both manager and director authority panels, the routine policy form, whole-dollar limits, policy preview/confirmation and actual employee names in Leadership activity.

Install uses a hash-checked source manifest, source backup and rollback; saved games are excluded. Restart the running game process to load 0.29.0. Next step: playtest renewal cadence, exception volume and the conservative owned-crew availability rule with larger portfolios.
