# Internal property specialists — 0.33.4

Managers and directors previously hard-coded outside contractors for tenant repairs, emergency work and flip renovations. Licensed real estate agents required a manually requested work product. The default now prefers a staffed home office, followed by other eligible owned providers, while retaining local-manager priority and all delegated authority checks.

## Delivered behavior

- The saved per-business `prefer_internal_property` policy defaults to true. Its visible label is **Prefer home-office and owned property specialists**, under Operations & recovery / delegated objectives. Disabling it chooses the outside route for future automated assignments; existing funded jobs continue unless cancelled. The existing routine-care `prefer_owned` opt-out also remains effective.
- Tenant repairs, emergency property work and funded flip renovations select an internal provider only with qualified, scheduled employees and enough capacity relative to the queue and work window. Electrical, plumbing and HVAC credentials remain necessary. Saved maintenance department coverage and staff assignments remain restrictions. Selected repair employees are recorded and only those qualified employees can deliver the work.
- Home-office maintenance staff can also perform basic cleaning and grounds care. They consume the same named time pool as repairs and office services, including travel and supplies; landscaping observes weather interruptions. Security still uses qualified service providers. Existing internal service pricing and consolidated eliminations apply. The earlier four-visit outside cleaning plan costing $576 is $461 in the whole-dollar interface at the existing internal rate, with real labor and supplies charged to the provider.
- A home office with an active real estate agent can deliver closing preparation using its existing office equipment at tools level 0. No department-creation fee or free completion bonus is invented. The automatic department becomes a saved record when work is requested; it is visible and editable beforehand. Configured departments replace the implicit defaults, including county and assigned-staff restrictions. Tool upgrades still cost $500 per added level.
- Planned flips request agent preparation before acquisition and sale marketing; marketed company-owned properties also trigger a request. Actual qualified preparation must finish before the existing one-closing, 90-day brokerage reduction applies. Staff time, leave, licenses, expertise, tools, queue load and allocated costs continue to govern progress. Buyer and seller accounts remain separate. No new preparation is booked when an agreed closing is too soon.
- Completed valid preparation is reused, pending work is not duplicated, and cancelled preparation selects ordinary closing fees. Agent work is checked against the property's county, rather than only the client's home county. Future labor allowances include estimated preparation time and are reduced as actual work is delivered.
- Internal flip materials come from the funded project reserve when booked. Future internal labor stays reserved and is released only as delivered. Insufficient remaining reserve prevents further unapproved work; it does not create money. Ordinary internal repairs retain future labor commitments. Named capacity is date-tagged so yesterday's exhausted hours cannot incorrectly force outside routing today.
- Leadership activity names the selected provider, reason, cash and commitment. Repair jobs remain in the property workbench and closing preparation in the service queue. No save migration or live campaign edit is required.

## Validation actually executed

The final combined run passed **227 tests** using the project's Python environment:

```text
python -X utf8 -B -m pytest
  tests/test_internal_property_services.py tests/test_context_forms.py
  tests/test_completion_systems.py tests/test_home_office_company.py
  tests/test_property_scale.py tests/test_manager_defaults.py
  tests/test_property_manager_scope.py tests/test_service_projects.py
  tests/test_repair_all.py tests/test_authority.py tests/test_manager_routines.py
  tests/test_director_inheritance.py tests/test_property_services.py
  -q -p no:cacheprovider --tb=short
227 passed, 2 warnings in 89.27s
```

The new cases cover provider priority, manager and director routing, licenses, leave, overload, explicit counties, funding, preference overrides, duplicate/cancelled/late agent work, real fee reduction at closing, actual internal costs, flip reserve reconciliation, independent reading, save/load and financial audit, two-day skip/day-step equivalence, dated capacity, cleaning/grounds resources, and preventing reuse of repair hours. Existing regressions include property sale gains/losses and consolidation. The two warnings are existing Starlette/AnyIO deprecations. The full repository suite was not run. A stale UI-test assertion tied to version 0.33.2 now checks the running package version.

Browser QA used separate seeded SQLite campaigns at port 8897. A manager assigned the home-office crew to an interior repair, requested the office agent without manual department setup, and booked the four cleaning visits with the office for $461. A week skip advanced two days and paused on the configured property-work completion event with zero approvals pending. The home-office queue showed named agent progress, and the audit showed actual provider choices, $150 repair materials and a separate future labor commitment. Editing the automatic agent department at tools level 0 produced a review with no immediate cash movement. Home-office and department screens were visually checked. No user save was used for testing.

## Limits and next step

Provider selection is a bounded capacity estimate, not a guarantee against later sickness, license expiry or workload changes. Started internal jobs retain their assignments; recovery may require staff changes, cancellation or outsourcing. Agent automation supports closing preparation, not a new leasing-agent simulation, and does not intercept an immediate manual player purchase. Pending agent work can delay a delegated flip until completed or explicitly cancelled. No-agent or late-closing cases retain ordinary brokerage fees. A configured maintenance department's staff and county restrictions can exclude an otherwise owned crew.

Restart the application to load 0.33.4 and advance time. Existing saves receive the default preference without rewriting explicit choices. The installer backs up source and changes source/tests/documentation only. A later increment can add reassignment of stalled internal projects and richer leasing-agent work.
