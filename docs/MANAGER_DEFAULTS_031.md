# Daily management defaults — 0.31.0

An available local manager now handles existing daily operating routines without requiring the player to create an authority contract or a headquarters. Explicit disabled delegation, individual opt-outs and saved limits remain effective. A company whose delegation was explicitly disabled has a visible **Let the manager handle daily work** action that preserves its other settings.

## Implemented behavior

- Managers fill existing vacancies, recruit when needed, replenish stock, accept projects, renew credentials, review eligible annual raises and resolve supported routine operating decisions. The existing manager-first/director-strategic hierarchy and parent director inheritance remain in place.
- Weekly price reviews and shift alignment, owned-property repairs and leasing reviews now default on. Individual saved automation flags override these defaults. Hiring retains qualifications, candidate acceptance, recruitment costs and joining delays; repairs retain materials, labor, licenses, disruption and time requirements.
- Existing collections and property-care routines now work with the default manager authority. Free reminders and installment proposals precede contingency collection agencies. Cleaning and grounds care use real plans and finite management/contractor capacity. Existing security plans may be renewed; new security coverage remains opt-in.
- Routine paid leave defaults to manager review: at most five scheduled days, at most 25% of scheduled staff absent, remaining entitlement and qualified same-role cover. Explicit supervisor relationships, including cross-company reporting, are respected. Managers cannot approve their own leave. Coverage, duration, authority and other exceptions appear in the decision inbox with the reason. Eligible requests for the next day are reviewed before advancing the calendar, then affect attendance and leave use on the actual date.
- Newly reported tenant repairs receive a same-day manager review before the time-skip pause. Booking authorized work suppresses only that request's initial interruption. Missed repair deadlines and unrelated safety events remain visible and can still stop time.
- Completed work is attributed to the acting employee in Leadership activity and the authority audit. Questions identify who asked, show the commitment, and retain approval and deferral controls. Manager questions replace duplicate invoice/tenant-repair items for the same action, with policy and recovery links.
- Long skips still stop at required player decisions. A manual single day remains available for recovery and rechecks current authority. Merely opening the inbox or a preview cannot authorize work or change the simulation.

## Default financial authority

All amounts below are fictional game tuning. Player-configured limits override them.

| Industry | Whole routine purchase ceiling |
| --- | ---: |
| General retail, engineering, property/service operations, banks and other industries | $2,500 |
| Boutiques and restaurants | $5,000 |
| Grocery, trades and logistics | $10,000 |
| Factories and construction | $25,000 |
| Gas stations | $50,000 |
| Car dealerships | $100,000 |

The default monthly salary ceiling is $6,000. Monthly cumulative authority is 20 routine purchase ceilings plus one annual salary at that ceiling and a $300 recruitment allowance. New pay is counted for the full year; future material and service commitments also count. The default headcount is the configured target or existing open positions. Project contract value is limited to $100,000. The normal weekly-hours cap stays at the existing 60-hour ceiling; automatic scheduling does not increase contracted hours.

The default grant covers only the employing business and its county. It preserves seven days of known obligations and any configured cash reserve without assuming future customer collections. Default routines adding no commitment may continue during a cash shortage. Explicit authority contracts retain their own forecasts, periods, scope and restrictions, including parent constraints. A manager beneath an explicit director contract still needs a compatible explicit grant; missing configuration does not bypass that director's controls.

Transactions cannot be split to evade a limit. The entire restock order or project-material requirement must fit. Authority usage remains in the existing audit when policies are edited; editing a policy does not reset spending. Actual cash constraints, protected deposits, payroll and other liabilities remain authoritative.

## Persistence and validation

Defaults are computed without altering saved configuration on a page read. Existing employee IDs, supervision, authority contracts, explicit opt-outs and financial records are retained. No save migration or live campaign edit is required.

The regression tests exercise real hiring, pricing, scheduling, collections, property work, leave approval and consumption, named inbox exceptions, cumulative commitments, geographic scope, financing restrictions, explicit opt-outs, save/load, daily replay equivalence and reconciliation. Browser QA used a separate seeded campaign and checked the management notice, inbox attribution, direct limit link, editable budgets and real approval preview without confirming it.

Executed validation: the full suite passed **579 tests**. After the final next-day leave and partial-policy preservation changes, **73 focused tests passed**, including all 14 new manager-default tests. A final rerun of the 14 feature tests checks the exact delivered source. The full suite log is retained in the staging workspace at `qa/full-tests-final.log`. The test environment reports two existing dependency deprecation warnings from the FastAPI/Starlette test client.

## Limits and next step

These are the existing bounded routines, not a general-purpose executive planner. Scheduling aligns ordinary shifts at the existing 08:00 start; turn off automatic scheduling when retaining a custom pattern. Hiring reviews run weekly, and decisions still require an available manager. Optional training spend, staff reductions, new locations, new financing, flipping and additional home-office service renewals require their relevant policies and authority. Delegated leases still require a current approved legal template. Recovery attempts and qualified repairs can fail or take time.

Restart **Play Empire Manager.cmd** to load 0.31.0. Check the business's daily-management status, retain or adjust its routine purchase ceiling, then advance time and review exceptions in the inbox. Future improvements can refine shift planning by industry and give managers richer supplier and cash-forecast choices without relaxing authority enforcement.
