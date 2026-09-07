# Manager leave queue — 0.32.1

Routine covered paid leave belongs to management. A three-day vacation affecting 20% of a five-person team fits the default five-day / 25% policy when qualified same-role cover and an authorized supervisor are available.

## Fix

Previously, a supervisor being unavailable on the current date made a future request a player blocker immediately. The game now keeps otherwise authorized requests in the manager's queue if that employee can review them before the requested start date. It derives the review date from actual schedules, paid holidays, existing leave and director workload without advancing the clock or writing to the save.

The manager approves only when available. The simulation then rechecks coverage, entitlements, policy and authority. Approvals reserve real days; attendance, paid/unpaid wages and reduced operating capacity still change on the actual leave dates. Long skips can reach the manager's next review date and still stop for separate financial or operating exceptions.

Explicit manual-review policies, limits, qualified coverage gaps, no reviewer before the start date, expired requests and self-approval restrictions remain player decisions. This is not blanket approval of all time off. Named primary supervisors, including cross-company relationships, remain effective. Completed requests and past approvals are preserved.

## Interface

- Decision inbox has a separate **With your managers** section for queued leave, showing the responsible employee and expected review date. These records are excluded from the player decision count.
- Genuine leave exceptions show **Why this needs you** prominently and link directly to the employee's expanded time-off policy.
- Employee time-off history labels pending requests as assigned to management or needing the player.
- New routine requests use a non-interrupting **Time-off request with manager** activity entry. The player-approval alert remains for exceptions.

## Validation

Executed **132 related regression tests**, all passing, covering leave, employee management, authority, directors, inbox, skipping and UI workflows. After the final activity-message change, **44 leave-focused tests passed**, including all **8 new cases**. The two existing FastAPI/Starlette test-client deprecation warnings remain.

New cases cover the five-person trades / 24-hour vacation example, an absent manager returning before leave, no reviewer before the deadline, changed authority and coverage, explicit manual policy, read-only queue/policy views, save/load and daily replay equality, actual leave consumption without duplicate approvals, and a funded/staffed long skip reaching the manager's review day. No full-suite rerun was performed for this targeted increment.

Browser QA used a separate seeded campaign, inspected the manager queue and exception explanation, followed the policy shortcut to the expanded five-day / 25% controls, and checked the rendered layout. The QA tab and server were closed afterward. The user's saved campaign was read only; its already-completed vacation was not rewritten. The saved team's current state qualifies under the default policy; it does not reconstruct every historical supervisor condition when the screenshot was taken.

Restart **Play Empire Manager.cmd** to load 0.32.1. Managers handle these requests as time advances; reading the inbox does not approve anything. A later staffing, leave or authority change can turn a queued request into a player exception. Future staffing improvements may offer cover arrangements; this increment retains the existing qualified same-role coverage rule.
