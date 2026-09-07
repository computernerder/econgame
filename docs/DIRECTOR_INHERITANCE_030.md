# Default parent-company director oversight — 0.30.0

Subsidiaries without an explicit director now inherit the nearest parent business's director. This applies through multiple ownership levels and updates immediately when ownership is rearranged. A director appointed explicitly at a subsidiary replaces the inherited director for that branch; deeper explicit assignments still take precedence.

## Player controls and behavior

- Business → Leadership and annual raises shows the director, payroll employer, linked source company, and combined workload. Management overview and employee hierarchies also show inherited oversight.
- Parent director inheritance is enabled by default, including in existing saves. Disable it at a business to stop inherited oversight for that branch. An explicit director at that business still covers eligible descendants.
- Remove an explicit assignment to return to the parent default. Explicit assignments already in saved games are preserved.
- Local managers continue to handle daily work. Directors handle strategic work and cover unavailable managers within existing permissions. An absent nearest director does not cause a more distant director to bypass their authority restrictions.
- Director oversight does not change any employee's primary reporting relationship or payroll employer. One employee, employment record, and payroll remain in place.

## Resources, authority, compensation and history

Direct and inherited businesses use the same director record, daily spending allowance, authority key, and cumulative monthly ledger. Each uniquely covered business reserves one hour per working day; explicit roots that overlap inherited scope do not double-count time or pay. The existing five-business ceiling and scheduled-hour limits apply to inherited scope.

New appointments check the full inherited workload and include its responsibility in the promotion-pay review. Ownership changes do not automatically alter agreed pay: uncompensated additional duties create the existing leadership-pay review in the decision inbox on the next simulated day. Scope changes are recorded in career history; repeat reads and unchanged day steps do not create duplicate entries. Old saves derive coverage immediately, then record newly inherited duties on a simulated day step.

New authority contracts default to the effective business scope. Saved business and county permissions do not widen when ownership changes or when an unrelated contract field is edited. Update those restrictions explicitly to authorize added scope. Existing parent-contract, purchasing, reserve, action and commitment checks still apply. The former parent director cannot act on a transferred subsidiary merely because an old contract still lists it.

If changed ownership or employee hours overload a director, delegated oversight is unavailable and the decision inbox links to management assignments. Long skips stop before advancing while that workload issue exists; one-day recovery remains possible. Overload discovered during simulation is also an unsuppressible stop event.

## Validation actually executed

- Initial existing regression set: 43 passed (leadership, authority, career history and ownership transfer).
- Full regression suite: 564 passed in 324 seconds, including the first 12 inheritance tests.
- Expanded inheritance suite: 14 passed, including two additional checks for switching parent directors and old-save history initialization. This includes the complete current inheritance test file after its test-fixture corrections.
- Browser QA used an isolated SQLite copy, not the player's active save. A parent-only assignment at Group Shared Services correctly covered three subsidiaries. Willow Plumbing & Electrical showed Quinn Sanders as inherited director and Morgan Lewis as the acting local manager. Disabling inheritance through preview and confirmation removed only inherited oversight there; another subsidiary retained its inherited director and the shared workload decreased from four businesses to three.
- Browser screenshots verified the inheritance controls and review dialog. Preview/read-only behavior, persistence, stable employee identities, daily replay, financial reconciliation, shared limits, explicit overrides, absence handling and overload stops are covered by regression tests.
- The suite reports existing Starlette/httpx and AnyIO deprecation warnings; no test failures remain.

## Limits and next step

This is inherited business-director oversight. Optional executive/VP scopes and employee reporting lines remain explicitly configured. The abstract legacy holding-company account has no employee director appointment of its own; a staffed home-office business can be the parent. Directors remain limited to five covered businesses, and saved contracts may need a scope edit before new subsidiaries can receive delegated actions.

Restart the game to load 0.30.0. No campaign database is migrated, reset, or advanced by the source installation. The next player step is to inspect the parent director and inherited workload in Management overview, then adjust any explicit overrides or restricted authority scopes as desired.
