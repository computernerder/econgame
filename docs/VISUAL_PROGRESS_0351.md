# Visual progress and financial readability — 0.35.1

The financial UI now draws the last 90 simulated days from the persisted journal.
No generated figures, historical market estimates, or simulation bonuses are used.

## Implemented

- Cash sparkline beside the persistent account balance. It always uses the selected account, even when viewing consolidated finances.
- Home shows cash and rolling profit for the selected owner and its current subsidiaries. Finances shows cash, net worth at book value, trailing 30-day earned income, and trailing 30-day profit. Owned business and single-owner property views also show relevant trends.
- Daily close values include real capital movements, debt, purchases, collections and accrued expenses. Profit includes recorded tax. Borrowing is not income and does not increase net worth. Consolidation follows the existing report eliminations and removes internal ownership stakes.
- Charts have whole-dollar values, named dates, pointer inspection, arrow/Home/End keyboard navigation, and expandable daily-value tables. Empty history is explicitly a single point. No external chart service or new package dependency.
- Two-column chart panels, compact balance summaries, expandable payroll and journal, visible buying links on Home, and a compact staffing-plan disclosure.
- Property purchase/ownership details precede long repair and development comparisons. Team heading precedes utility navigation.
- Leadership activity is a plain quiet link; Decision inbox remains the actionable count. Read tracking and the full manager audit are preserved.
- Business cards gain architectural illustrations appropriate to their industry family. Existing typography, colors, property art and custom comments remain.
- Financial account names, narrative business/property/employee references, care-invoice references and warranty labels are readable. Stored IDs and command payloads remain unchanged and displayed names are escaped.
- Mixed-use labels, property-count grammar and county filter button wording are corrected.

## Validation

Focused tests cover every daily cash point, reconciliation with stored balances and reports, internal-charge elimination, borrowing versus wealth, negative profit, read-only rendering, saved-game consistency, chart scope, empty history, name escaping and old-runtime restart compatibility.

Browser checks use an isolated seeded campaign, not the player's campaign. Desktop rendering, 390-pixel responsive layout without horizontal overflow, daily-value disclosure, and chart keyboard navigation were checked. Existing navigation, finance, leadership, campaign screens and server tests were also run; see the delivery report for actual totals.

## Limits and next increment

- Charts show up to 90 daily closes. A longer-period selector and historical market-value snapshots remain future work.
- Group history uses today's membership, explicitly labeled. It is not a reconstruction of the ownership tree on each past date.
- Book value is not market wealth or expected sale proceeds. Current market estimates remain on property detail screens.
- Some long operational forms and large employee tables still warrant further layout work. This is not a complete redesign of all management screens.
- The supplied study's repeated outsourcing of a small warranty claim, consistent inbox resolution controls, and purchase-success feedback are separate behavior/workflow follow-ups. This visual increment does not claim to fix them. Prioritize the legal spend-versus-recovery/retry guardrail next.

No save schema or simulation rules changed. Existing campaigns and daily-step/time-skip behavior remain supported.

## Delivery verification — 2026-09-07

83 focused Windows tests passed. All four groups of the complete GitHub suite and the image publication job passed in Actions run 34145385560. Build 2.1 (3781136) deployed through the guarded updater at 17:00:14 UTC, with backup build-2.1-20260907T170005Z. Normal browser sign-in, the saved campaign, live charts, readable invoice narrative and quiet activity link were verified at http://game.lan. The temporary local preview server was stopped after verification.

