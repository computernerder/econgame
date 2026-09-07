# Quieter time advancement — 0.33.7

Routine work no longer interrupts time by default. Completed repairs, training, employee starts, recruiting, renovations and expansions remain in the activity log. Missing preferences use a $1,000 financial threshold and no routine completion pauses. Explicit saved settings remain respected, including a zero threshold or routine pauses enabled.

The Advance time dialog now includes the routine checkbox, whole-dollar financial threshold and a **Use quieter skips** preset. Preferences save atomically with the advance command for period buttons, a chosen date or Resume. Closing the dialog alone does not save edits. Campaign settings retain the same controls.

Required owner approvals, exceptional time-off requests, unpaid payroll, breached delegated reserves, workload limits and business/campaign failure still stop advancement. No authority limits, commitments, cash rules, accounting or collection behavior are bypassed. Smaller financial issues still accrue their obligations and remain actionable. Other nonfinancial operating warnings can still stop time.

Handled manager issues and closed decisions no longer leave a stale pause behind. Reasons carry the relevant management/decision identity and recheck its status. A legacy boolean without an identifiable current unresolved event does not pause. Previous-day events are not replayed when an Engine instance is reused. Required reasons take precedence in the pause explanation.

An interrupted target is saved per campaign. **Resume to [date]** uses the normal advance command and all approval checks; a single recovery day preserves the farther target. Choosing a different multi-day target replaces the plan. Reaching the requested date clears the plan in the daily commit. Successful daily and batched simulation therefore retain identical economic state and no completed-plan bookkeeping differences.

The latest advance displays stop details and existing recovery links, plus counts of important updates recorded without pausing. These counts and the latest progress panel are session summaries; the pending target and individual journal/event records persist. The existing activity feed retains its recent-event window. No permanent historical digest or automatic approval is added.

## Validation

Tests cover default/explicit preferences, threshold boundaries, required guardrails, manager-resolved reasons, closed versus separate new decisions, real renovation completion, daily/skip equivalence, pending-target save/load and recovery, blocked resume, atomic invalid commands and duplicate HTTP requests. Existing completion/shortfall tests explicitly opt into their old interruption behavior. A blocked-skip assertion allows only its new target bookkeeping alongside the existing command receipt.

Browser verification used an isolated fixture: a month-long skip with routine pauses enabled stopped on renovation completion; the quieter preset changed the checkbox and threshold; Resume reached the original date. Controls, dollar formatting and stop links were inspected visually. The player's save was only read through read-only SQLite for diagnosis; simulation replays ran in memory with validation, without player approvals or writes to the save.

Executed validation:

- Initial full suite: `python -X utf8 -B -m pytest tests -q -p no:cacheprovider --tb=short` — 760 passed, four skip-plan bookkeeping failures in 442 seconds. Those failures exposed differing plan start dates/completed plans in daily-versus-skip comparisons and the expected new target on a zero-day blocked skip. The implementation now clears completed plans, stores only the pending target and leaves economic state identical. The blocked-skip test explicitly checks the saved target.
- Final affected-area regression: `python -X utf8 -B -m pytest tests/test_quieter_skips.py tests/test_skip_controls.py tests/test_game.py tests/test_property_manager_scope.py tests/test_internal_property_services.py tests/test_shared_resources_ui.py tests/test_manager_defaults.py tests/test_manager_routines.py tests/test_manager_leave.py tests/test_recovery_navigation.py -q -p no:cacheprovider --tb=short` — **162 passed** in 103 seconds, including all four former failures. This includes the 365-day daily/skip/reload reconciliation test.
- Additional focused checks: 49 passed initially; 36 passed for preferences, defaults and legacy opt-ins; 26 passed for final pending-target, shortfall and year-long equivalence checks. These overlap the final regression set and are not extra unique tests.
- Read-only diagnosis and in-memory replay of the latest campaign: 30 daily steps validated, from 2026-05-28 through 2026-06-27. This was not a long-skip bypass test: pending player decisions were left open.
- Browser: opted-in completion stopped after 15 days; quieter Resume reached the original date after 16 more days; a custom date completed another 28 days and retained a separately entered $2,000 threshold. No live campaign was advanced.
- Existing Starlette/httpx and AnyIO deprecation warnings remain; they did not fail tests.

## Installation and remaining behavior

Installation checks source hashes and creates a source backup with rollback support. Save files are not part of the installation. Restart the game after installing so the Python process, templates and versioned assets all use 0.33.7. For an older campaign with explicit pause preferences, choose **Advance time → Use quieter skips** before advancing.

Exceptions still need a player decision or a deliberate policy adjustment. This release changes interruptions and their presentation; it does not expand managers' authority or silently approve their requests. The next refinement should follow remaining *unhandled* inbox reasons, rather than suppressing required commitments.
