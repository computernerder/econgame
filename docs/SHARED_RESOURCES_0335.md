# Shared resources (0.33.5)

Home Office now presents staff as teams with specific uses. This extends the existing service queues, assigned employee time, property work and separate company books.

## Implemented behavior

- Team cards name their staff and show joining, leave, schedule and credential status. They explain ongoing support versus specific work products, county coverage, industry experience, existing assignments, current jobs and historical service-queue hours. Historical unused queue capacity is not presented as current availability or proof of idle staff. Actual banked specialist work is tied to its receiving account.
- Each team has direct task links: regular HR/IT/accounting/legal/purchasing/logistics/marketing support; recruiting, assessment, onboarding and succession; IT deployments/support; property repairs; agent closing preparation; and existing departmental work products. Opening a task selects the exact internal provider and matching product. The forms show relevant recipients/targets and internal delivery costs. Stale team/product links do not silently select a different provider.
- Schedule regular support creates an at-cost staff-access agreement when needed and reserves part of an existing employee shift in one reviewed decision. Existing agreements retain markup and access restrictions. The preview estimates costs; there is no outside service or setup fee. Active staff, credentials, owned operating recipients, county coverage, applicable roles, shifts, overlap and director time restrictions are checked before any agreement or history changes. Existing reservations are shown; a new form starts after a conflicting reservation where possible. Staff remain employed by their original company with one identity and payroll.
- Real assigned hours and ordinary attendance produce receiving-business benefits such as banked HR recruiting capacity. Charges settle between company accounts using the existing accounting path. Insufficient recipient cash remains an intercompany liability. Assignments appear in commitment forecasts, and reciprocal internal charges remain eliminated from consolidated profit. End support from a team card to return its time without terminating the employee.
- Maintenance cards also include actual repair and property-care workloads. Existing manager/director preference for qualified internal maintenance and agent preparation remains. Opening a task does not execute it or advance time; the ordinary review, confirmation, licenses and funding checks remain.
- Empty or restricted choices explain recovery, with links to the selected team's staffing/coverage. Configuration remains available beneath the teams and on their edit links. No save migration or live campaign edit is required.

## Validation

The combined regression run passed **280 tests** (120.51 seconds) using the project's Python environment:

```text
python -X utf8 -B -m pytest
  tests/test_shared_resources_ui.py tests/test_department_ui.py
  tests/test_ui_workflows.py tests/test_recovery_navigation.py
  tests/test_internal_property_services.py tests/test_context_forms.py
  tests/test_completion_systems.py tests/test_home_office_company.py
  tests/test_property_scale.py tests/test_manager_defaults.py
  tests/test_property_manager_scope.py tests/test_service_projects.py
  tests/test_repair_all.py tests/test_authority.py tests/test_manager_routines.py
  tests/test_director_inheritance.py tests/test_property_services.py
  tests/test_specialists.py -q -p no:cacheprovider --tb=short
```

After the final template/layout and version-guard updates, the five UI/recovery/shared-resource files passed **52 tests** (29.95 seconds). An additional property-care workload assertion passed its targeted test. The two warnings are existing Starlette/AnyIO deprecations; the full repository suite was not run.

Tests include read-only views and previews, real confirmation/save/load, existing markup/access restrictions, county/role/credential checks, overlap and director restrictions, leave, finite shared HR minutes, real internal work costs, reconciliation, commitment forecasts, ending assignments without changing employee identity, and two-day skip versus daily-step equivalence.

Browser QA used an isolated SQLite campaign at port 8897. A recurring HR allocation was reviewed and confirmed, appeared with its employee, recipient, hours and end action, and persisted through a server restart. A recruiting job opened with the exact internal provider, showed internal cost wording and account balances, and appeared alongside the recurring assignment after confirmation. Desktop and 390-pixel-wide team layouts were visually checked; a narrow navigation label was also prevented from wrapping into a tall column. Tests and browser QA did not modify a player save.

## Limits and next step

- Recurring support uses the existing same interval on each contracted working day; it is not a new weekly scheduling optimizer. The player selects the recipient and hours. Managers retain their existing automatic property/service decisions; this update does not grant new autonomous strategic authority.
- Costs and benefits still require actual work. Current county coverage and industry experience can restrict or slow delivery. The historical queue counters exclude work booked through other operating paths and are labeled accordingly.
- Property repair links select the employing contractor company. Existing repair rules choose qualified crews; licenses, materials, funding and competing work still determine whether the request can proceed.
- Future improvement: a weekly capacity planner across all teams, with manager recommendations for recurring allocations. No artificial automatic bonuses or universal free services were added.
