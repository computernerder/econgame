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

Pending final regression and browser checks; results will be recorded before release completion.
