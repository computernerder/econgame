# Employee management — 0.21.0

Open **All employees** for the team directory, named primary supervisors, current absences and the upcoming coverage summary. Open an employee for benefits, dated leave requests, approval history and cross-company reporting.

## Delivered behavior

- Vacation, sick leave, floating holidays, parental leave and unpaid leave use dated requests. Requests remain pending until approved, declined or cancelled. Future approved leave can be cancelled; leave already underway cannot be retrospectively cancelled.
- Paid banks show their current, reserved and available days separately. Approval reserves scheduled days; balances are deducted as those days occur. Weekends outside the employee's schedule and paid holidays do not consume entitlement. Overlapping requests and overspending reserved balances are rejected. Legacy immediate-leave commands also respect these reservations.
- Approved leave removes the employee's scheduled operating capacity, shared-service delivery and availability for management decisions on its dates. Pending or expired requests do not authorize absence. Staffing projections include approved future absences. The employee overview shows scheduled hours lost before skill, training and shared-assignment adjustments.
- Paid leave preserves base wage accrual. Unpaid leave removes wage accrual for its approved calendar dates, while employer benefits continue. Payroll tax follows the wages actually accrued. Forecasts account for approved unpaid dates and unavailable shared employees. This is a fictional game convention, not a real employment-law calculation.
- Vacation accrual distributes the complete annual entitlement across twelve months; it no longer loses the remainder when the entitlement is not divisible by twelve. Lowering a policy does not erase an already earned vacation balance. Annual sick/floating resets preserve existing approved reservations.
- Employees can request vacation during the monthly simulation. Requests are infrequent, deterministic and use a separate stable calculation rather than consuming economic random draws. Requests appear in the decision inbox and approval history.
- A business can allow automatic routine paid-leave approval with a maximum request length and maximum percentage of scheduled staff absent. An available primary supervisor or delegated leader must review it. They cannot approve their own leave, and same-role coverage must remain on every requested day. Existing authority contracts can prohibit or require player approval. Parental and unpaid requests remain player decisions. Automatic reviews run on the next simulated day; one-day advances remain possible with pending requests.
- Pending leave requests stop long skips and link to the decision inbox. Approved requests do not repeatedly require approval. Unapproved requests reaching their start date expire without taking leave or deducting balances; new future dates can be requested.
- Individual medical/dental plans, employer medical share, retirement contribution, vacation/sick/floating entitlements and paid holidays can override unlocked employer policy. Parent policy locks still apply. Employer benefits can be restored with one action. Changes affect future payroll; annual entitlements do not immediately refill existing banks.
- An employee can report to an active employee in another owned company, including the home office. The named supervisor follows the employee identity through promotions. Payroll, ownership and financial authority remain separate. Self-reporting and reporting cycles are rejected. The chart shows cross-company context cards with the true employer and keeps local employee counts separate. Supervisor departure or divestment returns the relationship to company leadership during the daily reconciliation.
- Generated employees have unique human names without numeric suffixes. Existing numbered or duplicate names receive deterministic replacements during migration; person IDs, employments, salaries, history, ownership and ledger balances remain intact. Historical narrative text is retained as recorded.

## Persistence and compatibility

The first opening of an older compatible campaign creates a `before-employee-management-*.sqlite3` backup before adding the version marker and replacing numbered/duplicate names. The upgrade is transactional and runs once. This update does not edit the live save during installation. Restart the game launcher to use the updated code and perform the save upgrade.

The original handoff and custom comments are retained. Earlier working immediate-leave commands remain compatible, with overlap and reserved-balance checks. Employee benefits, payroll and organization changes extend their existing systems.

## Validation

The dedicated employee-management tests cover five leave types, actual work/payroll effects, reservations and cancellation, overlaps, holidays, cross-company reporting and cycles, supervisor departure, delegated approvals and authority restrictions, absent shared staff, benefits and parent locks, naming and migration, UI rendering, long-skip blocking, replay/save consistency, complete annual vacation accrual, expired requests and seeded employee requests.

Executed results and the final test count are recorded in `EMPLOYEE_MANAGEMENT_021_VALIDATION.md` after validation. Browser testing uses an isolated copy of the existing campaign, not its live save.

## Current limits

Leave is recorded in whole calendar dates, with bank usage in scheduled working days; partial shifts and hourly leave banks are not modeled. Approval coverage is a same-role/headcount check, not a replacement-shift optimizer. Parental leave follows the existing simplified annual fictional entitlement. Sick and other non-vacation requests can be entered on the employee's page; only vacation requests are generated proactively. A reporting relationship alone does not delegate hiring, spending or growth authority.

Next suitable increment: partial-day leave, named shift-cover assignments, and more detailed supervisor workload accounting, using the same request records and approval checks.
