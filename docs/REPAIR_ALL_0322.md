# Repair all (0.32.2)

Property workbench → Book property work now has a visible **Repair all** button beside current system conditions. It opens the normal confirmation for the selected property and contractor, with each included system's condition and price, combined payment, hours, skipped systems, and the paying owner's remaining cash. The System selector also offers all systems needing repair. Property and contractor changes refresh the estimate.

The action books one ordinary repair for each system below 100 condition that has no work underway. Systems at 100 and active work are skipped. Every job retains its own saved identity, materials, prepayment, remaining labor, qualification, license, workmanship and accounting records. No condition changes at booking. Ordinary repairs add up to 15 condition points before workmanship effects; they do not promise restoration to 100. Existing callback risks remain.

All jobs are validated and the combined cash cost checked before the first posting. Invalid ownership, unfinished buildings, empty lots, insufficient cash or an unqualified contractor leave the entire batch unchanged. Internal crews must cover every included system's qualification and valid trade license. Their work competes for real hours and charges actual labor as delivered. The owner still handles only one basic system at a time. Delegated previews assess the entire batch commitment against authority, rather than approving its component jobs independently. This update adds no new autonomous spending policy.

The existing action revision and command identity checks protect confirmation and retries. No save migration is needed. Cash remains in cents internally; the interface uses whole dollars. Installation changes source, tests and documentation only, with a verified source backup and rollback.

Validation executed:

- 16 feature tests passed: real completion and prepayment reconciliation, active/full-system exclusions, aggregate cash failure without partial writes, qualification/license/ownership/building/owner restrictions, finite shared employee hours and matching internal charges, read-only preview, confirmation retry, persistence, seeded daily progression against individual repairs, and aggregate delegation limits.
- 111 existing regression tests passed across property condition context, property scale, property services, completion systems, authority, UI workflows, whole-dollar display and template restart handling.
- The combined initial run had 126 passes and one new test-fixture failure: the fixture injected subsidiary equity without the corresponding parent investment. After changing the fixture to use the real funding action, all 16 feature tests passed. No production simulation change was needed for that correction.
- Browser QA on a separate disposable save: six eligible repairs previewed for $5,820, while existing roof work and a 100-condition exterior were skipped; confirmation reduced cash from $169,693 to $163,873, retained the roof job, created six jobs, and disabled Repair all while every eligible system had work underway. The confirmation layout was visually inspected.

Limits: this is a selected-property batch, not a portfolio-wide command or automatic repeat-until-perfect program. It uses one selected provider; a provider missing a required trade license cannot silently subcontract part of the batch. Outside jobs use the existing parallel three-day crew model; internal timing depends on actual staffing. Future work could offer mixed providers or a target-condition budget, separately reviewed before spending.

Restart the game after installation to load the new runtime and templates.
