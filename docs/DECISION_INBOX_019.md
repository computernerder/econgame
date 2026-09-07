# Unified decision inbox — 0.19.0

Decision inbox is now always visible in the main navigation, with a count that refreshes during time advancement. It gathers current player decisions across controlled businesses and properties, independent of the selected account. Cards identify the affected account, deadline, recorded exposure or proposal amount, and available response. Overdue items appear first; deferred approvals remain visible separately from the attention count.

Coverage includes existing campaign decisions and management approvals; tenant, property-sale and supplier offers; unsuccessful vacancy advertising; lease renewals, overdue rent and refundable deposits; tenant repair requests and actual repair covenants; blocked closings and funded flip next steps; overdue internal and outside service work; workmanship claims and overdue customer invoices; dated unpaid obligations, loan arrears and delegated reserve breaches; closed-business asset recovery; startup staffing gaps, recruiting results, required credential renewal and overdue annual raises; and manual project/inventory decisions when automation is disabled.

Review links open the relevant screen with the affected record selected and its form expanded where available. Financial and operational commands retain their existing review, validation, funding and authority checks. Offers can be declined individually. Deferred management requests can be returned to review early and reopen after their deferral expires, without granting approval or spending money. Existing required-approval and financial skip stops remain enforced.

Cards derive from real saved records and clear when handled on another screen. Reading the inbox changes neither simulation state nor random outcomes. No second persistent queue, fabricated decision, financial posting or migration is introduced. Declines and deferrals update their original records and survive save/load. Source history and custom comments remain preserved.

Limits:

- Optional purchases and upgrades are available on their normal screens; the inbox prompts outstanding decisions and active workflow issues, rather than every possible optional action.
- A proposal, cash claim and amount owed have different cash effects. Recorded exposure is not presented as a combined bill.
- Unpaid obligations and unresolved work cannot simply be dismissed. Some cards lead to recovery or policy screens with several choices instead of one recommended transaction.
- Existing native resolution history remains available; this update does not invent a historical resolution log for every older offer or workflow.
- Future simulation features must add their outstanding decision sources to the collector. Filtering and pagination are possible later UI improvements.

Validation executed:

- Full regression: 356 passed in 171.46 seconds; two existing dependency deprecation warnings.
- Fifteen dedicated tests cover offer acceptance/decline and ownership, prefilled links and count endpoint, real repairs, renewals versus normal rent accrual, expiry, deferral/reopening and required approval stops, overdue work/payment resolution, hidden lease identity, legacy save/load, read-only state/RNG/ledger, unsuccessful advertising, rent payment plans, credential courses, and the funded flip-to-marketing lifecycle.
- Browser QA on a disposable copy of the campaign verifies the main navigation badge, actual management approval, review dialog, deferral, return to review, and unchanged cash. The live campaign is excluded from the source installer.

Next: extend the same source-derived inbox whenever another decision-producing workflow is added; keep optional growth browsing separate from required reviews.
