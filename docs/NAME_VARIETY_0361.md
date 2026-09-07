# Name variety — 0.36.1

People now draw from 261 first names and 301 surnames (78,561 two-part combinations). Selection avoids repeated first names and surnames where alternatives remain, preserves stable person IDs, and never adds numeric suffixes.

New businesses use industry-specific names; properties, empty lots, tenants, competing firms and supplier proposals use broader fictional naming catalogs. Vermont county names remain actual geography. Player-chosen company names and existing saved display names remain intact. Included property descriptions use the generated owner's name.

Naming uses a separate deterministic hash, preserving economic RNG draws and outcomes. A new-game form suggests a fresh editable seed each time; entering the same seed reproduces that world. API callers omitting a seed retain the established deterministic default. Changing a seed does not rename an existing save.

The catalogs are finite and stylistically regional. Existing campaigns retain familiar names; newly generated entries use the expanded catalog. This release does not change demand, staffing, market inventory or simulation balance.

## Latest usability study follow-up

Source: user attachment d71f2ebf-7d1f-4f52-92f0-fee2da25584d, received September 7, 2026. Previously addressed findings should be verified against the live build before being reopened. New findings remain open, separate from this naming release:

- Reproduce the reported monthly cash-change/ending-balance confusion and inconsistent skip cash delta. Trace dates and account scope before changing calculations.
- Consolidate duplicate hiring forms across Operations and Team.
- Clarify organization hierarchy scope and active navigation.
- Balance the new-game home page for business-only starts; make management tools less property-centric.
- Improve benefit-summary wording and grouping.

## Validation

- Windows: 65 tests passed across naming variety, employee management, saved games and property scale. After final naming polish, 21 naming/usability tests passed.
- Nine new tests cover unique people, cross-seed variety, replay, saved identities, RNG/ledger independence, tenants/suppliers/competitors and seed controls.
- Browser: created a disposable game with explicit seed 8317; confirmed varied market names and saved seed. Reloading the new-game form suggested two different seeds without changing the saved seed. Checked the rendered business market at desktop width.
- Existing player saves were not modified during browser QA.
- Source backup before install: backups/before-naming-0361-20260907-140911.zip.
- First GitHub run found two older tests tied to fixed labels: Northbank Enterprise Group and Household tenants. Updated them to locate the ownership root through market-parent relationships and verify occupied rental state, named tenant and active lease. All 11 organization/property-category tests passed locally; other first-run shards passed.
- Corrected full-suite release: https://github.com/computernerder/econgame/actions/runs/34150815972. All four groups passed: 204 + 220 + 188 + 241 = 853 tests; image build and startup/health checks passed.
- Deployed Build 5.1 / v0.36.1, revision a7ff108cbbf5a2e346266c7701b0138ffab8df9b, at 2026-09-07T18:19:31Z.
- Unraid save backup: /mnt/user/appdata/econgame/backups/build-5.1-20260907T181922Z.
- Live browser verification at http://game.lan: Build 5.1 badge, normal sign-in, saved-game list, original Willow Corner Market name and cash balances, and a fresh suggested seed on the new-game form. No new live campaign or gameplay action was created for QA.
