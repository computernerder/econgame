# Manager property coverage — 0.33.3

The reported four-visit, $576 cleaning request was incorrectly blocked by default geography: the manager's implicit grant included only the business's home county, even when that business owned the property. Default manager and director grants now include counties of properties owned by the businesses in their organizational scope. Local managers retain priority over directors. Buying a building grants no control over its tenants or another owner's assets.

## Implemented behavior

- Default coverage follows current ownership. Saved explicit county restrictions and parent authority contracts remain unchanged and enforced.
- Existing open, generated property-care requests are recalculated from current care needs, service plans, prices and available providers. The normal booking path checks the responsible employee, shared daily workload, transaction and cumulative budgets, financial commitments and cash reserves.
- Only currently executable routine care appears as “With your managers” in the inbox and leadership activity; it does not count as a player approval or block a long skip. Reading a page uses an isolated preview and changes no saved state or cash.
- Daily advancement repeats the checks before advancing the date, books real service jobs, charges the property owner's company, resolves the old request and records the responsible employee, cash spent, commitment and result. Long skips use the same daily path.
- All pending care is previewed together so separate requests cannot each claim the same budget or employee time. Leader previews use delegated simulation context, avoiding the player's limited discretionary allowance while doing owner repairs.
- Explicit disabled automation, deferrals, insufficient cash, absent managers without director cover and restrictive budgets still prevent execution. Genuine exceptions remain in the decision inbox.

## Validation actually executed

Using the project's Python environment in the isolated source staging directory:

```text
pytest tests/test_property_manager_scope.py tests/test_manager_routines.py
       tests/test_manager_defaults.py tests/test_director_inheritance.py
       tests/test_authority.py tests/test_leadership_activity.py
       tests/test_property_services.py tests/test_leadership_transfer.py
       tests/test_manager_leave.py -q -p no:cacheprovider --tb=short
139 passed

pytest tests/test_property_manager_scope.py tests/test_leadership_activity.py
       -q -p no:cacheprovider --tb=short
25 passed after two additional edge cases and the final activity template change
```

The runs cover 141 distinct tests, including 16 cases in the new scope test file. The latter verify real $576 company payment; unrelated tenant/personal asset boundaries; explicit manager and parent restrictions; director absence cover; monthly competition; opt-outs and deferrals; read-only inbox/activity; saved-state reload and financial audit; two daily steps matching a two-day skip; zero-day long-skip blocking for an explicit restriction; and independence from the owner's repair decision allowance. Two existing Starlette/AnyIO deprecation warnings remain. The entire repository suite was not run.

Browser QA used a separate seeded SQLite game at port 8897. The inbox showed zero player decisions and one manager-care request. Advancing one day booked four cleaning visits without an approval dialog, kept the inbox clear and showed the named manager's completed action with $576 cash and commitment in Leadership activity. Inbox and management screenshots were visually checked. No live campaign was used for testing.

## Limits and next step

Automatic retries apply to generated property-care requests, not every historical management exception. Obsolete requests (for example, work already booked manually or a property sold) are not silently marked successful. An employee must be available now for a request to leave the player approval count; this increment does not schedule an absent manager's future return. Personal-property care remains manual, and preserved explicit scope restrictions may still require an edit through the existing delegated-limits link.

Restart the installed application to load 0.33.3, then advance time. Existing saves require no migration; the installer changes source, tests and documentation only and backs up replaced files. A later improvement can reconcile obsolete proposals and schedule routine questions for returning managers without weakening authority checks.
