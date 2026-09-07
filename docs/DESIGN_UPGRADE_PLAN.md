> Current release: **0.14.0**. See [Property service businesses](PROPERTY_SERVICES_014.md), [Contracts and purchasing](COMMERCIAL_CONTRACTS_013.md), [Service projects](SERVICE_PROJECTS_012.md) and [Operations release](OPERATIONS_RELEASE_011.md) for delivered behavior, accounting and remaining scope. The inventory below is retained as historical handoff context.

# Design extension inventory and delivery gates

Updated 6 September 2026. The user's new design supersedes conflicting older defaults, including D002's absence of a campaign-ending insolvency outcome. The original handoff and custom comments remain intact. This document records implemented behavior separately from the remaining design. Release 0.10.0 is increment 1 only.

## Inventory before this increment

The code and HANDOFF_TEXT.txt, DESIGN_DECISIONS.md, FULL_GAME_STATUS.md and validation history were inspected first.

| Area | Working foundation | Material gaps |
| --- | --- | --- |
| Ownership scales | Optional holding company; personal property play; businesses own property and subsidiaries; separate rent counterparties; book-value business transfers; employee IDs and reporting charts | Legal entity still generally maps to one operating business/location; multi-operation entities and richer location separation need a migration |
| Money and time | Integer-cent double-entry journal, separate ledgers, internal eliminations, SQLite atomic daily commits, seeded subsystems, Friday payroll, dated invoices, debt schedules, explicit loan guarantees | No obligation aging lifecycle or complete failure/resolution; many recurring costs modeled as one payable account |
| Delegation | Working employee managers and directors, finite reserved employee time, shared daily director limit, annual raises, hiring/training/stock/project/growth automation, approval requests | No VP designation/strategy allocation; no common monthly/parent/committed-cash enforcement before this increment |
| Shared services | Qualified local/shared employees consume real time; allocations and reciprocal charges; seven support-role effects; paid reporting and legal work credits | Credits and daily effects are not a department queue; no tools/industry coverage/work scheduling or full outsourcing/unused-capacity service costing |
| Legal | Legal licenses, finite earned hours, acquisition asking-price adjustment | Current discount is guaranteed; no original offer/counterparty refusal/factual obligation workflow. Do not claim it meets the new legal design |
| Property | Purchased buildings and space leases, deposits as liabilities, tenant arrears, internal premises, rehabilitation, delayed sale closing | Limited categories; no differentiated tenant offers, system-level condition, detailed repairs or market-contingent flip workflow |
| Financing/banks | Loan assets and deposit liabilities, defaults, liquidity reserve, owned-bank loans actually transfer lender cash, explicit guarantee payments | Capital adequacy and loan underwriting need a broader constraint review before autonomous financing |

### Industry behavior inventory

Retail/boutiques, grocery, gas stations and dealerships use constrained inventory sales with different role coverage and unit economics. Restaurants use simultaneous kitchen/service capacity; perishable inventory can waste. Engineering, trades, construction and factories consume qualified work and project materials, earn unbilled revenue, invoice on completion and collect later. Property management earns serviced-unit fees; rentals earn actual property rent; self-storage has finite occupied units. Logistics has fleet/driver/dispatcher capacity and internal transport displaces outside delivery. Banks carry customer deposits and loans and can incur defaults.

Remaining industry work is substantive: dealership lots need vehicle cohorts and aging; construction needs estimates, contract milestones, rework and uncertain collection; factories need separate production/capacity/quality/maintenance; groceries need richer spoilage and purchasing choices; all industries need explicit competition/customer relationships, equipment progression, working-capital warnings and recovery decisions. Existing names or multipliers do not satisfy these requirements by themselves.

## Increment 1 delivered: delegation and cash commitment boundary

Implemented in authority.py and integrated with Leadership, automatic stock orders, automatic project acceptance, time skips and Management overview.

- Saved manager/director contracts with business and geographic scope, optional parent, per-action allow/approval/prohibit, transaction and project-value limits, monthly cumulative commitments, headcount including joining employees, compensation bands, forecast horizon and minimum uncommitted cash.
- New grants cannot exceed their parent's scope, limits or permissions. Existing child grants are constrained live after a parent tightens. Children charge the same parent's monthly budget. Changing a contract does not erase recorded spending.
- Actual proposed actions are checked on a clone, including verified cash expense and annualized added base salary. Understated director cost estimates cannot bypass limits. An order is refused in full rather than split to fit authority.
- Cash forecast lists accrued obligations, protected customer deposits, known payroll/benefits/tax including scheduled overtime and shift premiums, property/rent/overhead, assigned shared-service charges, loan installments and full remaining accepted-project materials. It assumes no collections or new sales. Existing paid project budgets are not charged twice. The forecast is not a ledger posting or consolidated profit report.
- Cash-preservation objectives escalate hiring/growth; growth objectives permit these only when the existing growth/hiring policy and all authority checks allow them. Balanced and growth currently share the same underlying weekly growth planner; no claim of sophisticated executive judgment.
- Audit records actual employee ID, business, date, action, cash outflow, commitment and charged authority ancestors. UI shows the most recent ten; persisted audit is retained.
- Requests include cost, explanation, recommendation, risk and review date. Review dates never automatically grant authority. An explicit seven-day deferral suspends that action without erasing accrued obligations.
- Required approvals and cash reserve breaches always stop skips. Existing open requests prevent a long skip from advancing another day. A one-day step remains available for recovery and never authorizes a blocked action.
- A single manager can report to the player. No headquarters or holding company is required. Existing campaigns retain their previous authority settings until the player reviews and saves the stronger contract.

Acceptance: scope and parent limit checks; cumulative spending across days; clone rejection without partial journal changes; incoming payroll and deposits; project acceptance before new commitment; saved contract/rendering; deterministic continuation with reload; full existing regression suite. See VALIDATION.md for the actual commands and outcomes.

### Increment 1 limitations

This is a conservative cost forecast, not a complete dated cash-flow scheduler. Accrued bills are treated as reserved immediately, even when their contractual due date is later. Loan future interest is conservatively estimated; future variable incentives, inventory orders, uncertain repairs, lease renegotiations, and uncalled guarantees require reserves. Future service receipts are not assumed. No general external purchasing supplier constraints, autonomous financing, VP role, forecast confidence model, leader incentive/judgment model, or permanent failure system was added here. Audit retention needs indexing/compaction before decade-scale growth.

The legacy direct automatic bank/customer lending model remains governed by its existing bank policy and liquidity controls, not the new manager purchasing contract. Autonomous acquisitions, new debt and larger corporate expansion remain player actions pending subsequent gates.

## Next increments, in dependency order

1. **Dated obligations and actual distress.** Introduce contractual due/overdue records reconciled to ledger liabilities; warnings, missed payroll/supplier/rent/debt consequences, financing and recovery choices, subsidiary closure, and parent campaign-ending insolvency. Transmission to owners only through explicit guarantees/funding commitments. Preserve recoverable assets, receivables, employees and historical ledgers. Verify profitable-but-illiquid failure, funding recovery, isolated subsidiary failure and explicit-guarantee exposure. Complete bank capital adequacy before expanding delegated lending.
2. **Staffed service delivery.** Replace work credits/daily effect caps with prioritized tasks, assigned qualified staff, effort, tools, industry/geographic coverage, deadlines, queues, outcomes and unused HQ capacity. Support internal, outside and mixed delivery for HR, IT, maintenance, legal, accounting, finance, purchasing/logistics, marketing, training/operations. Home Office Director first, optional Corporate Services VP later; preserve one primary employee reporting relationship. Verify overload delays and exact cost allocation/elimination. Basic financial reporting remains available from the start.
3. **Legal work products.** Persist original offers, obligations and claims before investigation. Reviews identify existing facts; negotiations can be refused, collections can fail and specialists/outside counsel consume real time/cash. Show settled recoveries, documented price/term concessions, unresolved exposure and costs separately; future concessions never count as current cash. Retire the guaranteed discount workflow after compatible migration.
4. **Property operations.** Residential/commercial/mixed-use/office/industrial categories, persistent units/spaces and tenant prospects, leasing/renewal concessions, realistic vacancy marketing, collections, complaint/repair requests and delegated portfolio operations. Show occupancy, collected rent, operating income, cash after debt, deposits, arrears, maintenance and value separately. Buying buildings never acquires tenants' businesses.
5. **Property systems, repairs and flips.** Structure, roof, plumbing, electrical, HVAC, interior/exterior and specialist equipment; deterioration, uncertain inspections of preexisting facts, qualification/material/travel/time/disruption requirements, callbacks and maintenance/repair/replacement/conversion choices. Flips have inspections, budgets, contingency, holding costs, conditional offers, negotiation, failed financing, marketing time and downside cases; profit excludes loan proceeds and distinguishes principal/interest/investor cash. Verify both profits and losses.
6. **Internal contractors and industry completion.** Internal construction/trades/engineering/service work consumes the same capacity/materials as outside work; eliminate internal profit. Complete the industry gaps above and single-location progression (equipment, customers, people, services, efficiency, improvements, debt reduction). Implement VP coordination and bounded strategy only after underlying proposals/commitments are reliable.

District development remains explicitly later: land assembly, feasibility, approvals, financing, phased construction, preleasing and district improvements. Minority/public equity, multiplayer, historical-era research and installer performance qualification also remain outside this increment.

Each increment must include simulation behavior, persistence, usable controls, relevant seeded tests, cash/profit reconciliation, daily-step/reload equivalence, honest limitations and a fresh validation entry. Do not substitute dashboard constants or guaranteed success messages for these gates.
