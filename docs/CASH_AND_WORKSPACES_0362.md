# Cash reconciliation and clear workspaces — 0.36.2

Source: user usability session attachment d782be7c-e63c-4998-91ac-5216a27d896c, September 7, 2026. Preserve the reverified purchase confirmations, construction cost breakdown and charts.

## Behavior

- Completed skip summaries show the selected account's actual cash before/after, delta and date interval. Group cash change remains explicitly labeled separately. The values are frozen at skip completion, so a subsequent purchase cannot rewrite the prior skip's result. API polling and server-rendered summaries use the same read model. Cancellation and zero-day blocks reconcile too.
- Monthly finance cash change reconciles opening cash plus movement to current cash. The personal starting endowment and custom scenario starting capital are opening balances; later contributions, acquisitions, purchases, financing and withdrawals remain movements. Ledger entries and profit are unchanged. Consolidated internal transfers cancel as before.
- Business Operations, Team, Properties and Finances retain the Businesses sidebar context. Ownership and Services are explicit links to the shared Organization and Home Office workspaces instead of anonymous business tabs. Those workspaces state the selected account, highlight their actual sidebar destination and offer a return link.
- Team owns the guided hiring form. Operations retains the staffing requirements and links directly to Team. Properties links to Finances instead of repeating its charts; compact Operations/Home charts remain.
- Employee benefits show separate Medical, Dental and Retirement rows. Absent coverage says Not provided. A medical employer-share percentage appears only when a medical plan exists; high-deductible plans have a readable label.

## Validation and limits

Six regression tests cover starting capital, next-month funding, sandbox/custom dates, consolidated transfers, save/load reporting, scoped skip/API reconciliation, frozen summaries, cancellation, navigation, duplicate controls and benefit states. Existing chart and navigation assertions reflect the intended new arrangement. Local results and release checks are recorded below.

Browser QA used a disposable campaign: personal cash change $0 versus store/group +$1,615; the selected account and before/after values agree. Checked business tabs/sidebar, one Team hiring panel, employee benefits and shared Home Office context. No live game actions were used for QA.

This changes reporting and navigation, not cash transactions or staffing behavior. Cash movement includes financing and transfers and is not profit. Whole-dollar display retains cent-accurate internal values. Group membership can change group cash totals when an acquisition or sale completes. Completed skip digests remain session-local as before and reset on server restart. Shared workspaces deliberately reuse one implementation and retain access to group providers; this is not a redesign of service queues or employee hierarchy.

Local validation: 88 tests passed across cash context, navigation, charts, skip controls, employee management and the core game suite. Browser checked the selected-account summary, correct sidebar/tab states, benefits wording and shared-workspace return link. Source backup: backups/before-usability-0362-20260907-150317.zip.

The first full GitHub run (34154102687) found one historical workflow test requiring duplicated hiring controls. It now follows the Operations → Team link and verifies the single specialist picker, HVAC/HR options and policy shortcuts there. All 11 workflow tests passed locally; the other three full-suite groups passed.

Corrected release run: https://github.com/computernerder/econgame/actions/runs/34154440172. All 859 tests passed (259 + 239 + 185 + 176); image publication and startup/health checks passed.

Build 7.1 / v0.36.2, revision 40db810a6a1a60e8ab65ba357bbe4ca3f54a3125, deployed at 2026-09-07T19:14:17Z. Save backup: /mnt/user/appdata/econgame/backups/build-7.1-20260907T191408Z. Image: ghcr.io/computernerder/econgame@sha256:2739083880879aa1f85e079ad7328172bdb1c5f1c06ecb323267119a2d1acd4c.

Live verification at http://game.lan: normal sign-in, Build 7.1 badge, personal monthly change -$87 with $70,485 opening and $70,398 current cash, Businesses sidebar highlighted on the business Properties tab, four business tabs and no duplicated Properties charts. Existing saved names remained intact. No live gameplay action was performed; next time advance will populate the new scoped skip digest. Local QA server was stopped.
