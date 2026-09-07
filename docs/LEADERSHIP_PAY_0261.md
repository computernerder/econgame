# Leadership promotion pay — 0.26.1

Appointing an employee as a director now includes a prospective salary increase in the decision review. The original employing company pays the higher wages through normal payroll. Employment identity, primary reporting line, accrued wages and the annual review date are preserved.

## Behavior

- First director or Home Office Director appointment: 15% base-pay raise. First VP appointment: 25%.
- Each additional business beyond the employee's previously compensated scope adds five percentage points of responsibility. Only newly added responsibility is applied as a percentage of current pay. For example, a $3,400 director becomes $3,910; adding a second business raises that to $4,105.50 internally (displayed as $4,106).
- Previously compensated responsibility is credited when changing roles. Moving from a one-business director to a one-business VP adds 10%, rather than another full 25%.
- Repeated appointments, spending-limit edits and removing/reassigning the same scope do not stack raises. Removing duties does not reduce agreed pay.
- Hourly employees receive the corresponding hourly-rate increase, rounded up to whole cents. Existing compensation extras remain in place.
- The review shows old/new monthly base pay, monthly and annual increases, the paying employer and total monthly employer payroll change. Employer taxes and applicable overtime are additional to the quoted base-pay increase.
- New salaries flow into payroll accruals and cash forecasts. Appointment itself does not move cash or retroactively change earned wages.
- Directors and executives in older saves who have no recorded responsibility-pay credit receive a deduplicated decision-inbox request on the next simulated day. Approval rechecks current duties. Removing all relevant duties resolves the request. Existing approval/skip guardrails apply.
- Pay credit persists in `world.systems.leadership_pay`, keyed by stable employment ID. No save rewrite is required during installation.

## Validation actually executed

107 tests passed across leadership pay, leadership, authority, leadership activity, campaign product, completion systems, financial detail and management. Nine new promotion-pay tests cover payroll/forecasts, hourly compensation, expanded scope, rejection without mutation, legacy approvals, removal, executive promotions, read-only previews and save/load reconciliation. Two existing tests were updated from unchanged salary expectations to the new director/VP raises; employee identity and capacity assertions remain.

Browser QA on an isolated game confirmed the $3,400 to $3,910 appointment review, +$510 monthly / +$6,120 annual base-pay cost, unchanged $11,933 cash immediately after confirmation, and a repeated review with no additional raise. Two existing dependency deprecation warnings remain. The full repository suite was not rerun for this increment.

## Limits and next step

Raise percentages are fictional gameplay defaults, not negotiated offers or labor-market guidance. This increment does not add promotion negotiations, refusal/morale consequences, retroactive back pay, salary cuts after reduced duties, or enforcement against subsequent manual salary reductions. Like existing compensation changes, promotions have no immediate cash charge; increased future payroll can create financial distress. A future compensation-policy increment can add configurable bands and employee counteroffers.

Restart the game after installation. Existing unpaid leadership responsibilities appear for review after advancing a day.
