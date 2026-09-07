# Vermont counties — 0.24.0

The setting is Vermont, with all 14 counties available for properties, business locations, employee home locations, service coverage, community projects and delegated geographic scope. Property pages use a county dropdown that retains ownership scope, property type and portfolio filters. The overview introduces Vermont and the management navigation names Counties & community.

Existing geographic references migrate as follows:

| Previous region | County |
| --- | --- |
| Willow Creek | Rutland County |
| Northbank | Chittenden County |
| Parkside | Washington County |

The remaining counties are Addison, Bennington, Caledonia, Essex, Franklin, Grand Isle, Lamoille, Orange, Orleans, Windham and Windsor. Each new county has residential, commercial, industrial, office and mixed-use listings, plus starter and larger development lots. Players can start existing industry types in any county through the existing opening workflow. Expanded catalogs supply future monthly listings.

The migration preserves existing business and property identities, names, ownership, values, condition, balances, employee identities, pending work and saved random streams. Structured geographic fields in departments, authority grants, community work and pending action arguments are remapped without broadening geographic authority. Existing county economic history transfers with its original region. Custom business names and historical journal text are retained. Legacy bookmarked filters and action geography are normalized to county names.

The database gets one immutable recovery backup before migration, which is atomic and runs once per campaign when that campaign is opened. The source installer does not open or change live saves. Geography uses its own persisted version marker, matching earlier incremental feature migrations; historical JSON catalog fingerprints remain intact for compatibility with older save upgrade paths. The runtime applies Vermont geography to those catalog records after calculating historical fingerprints.

Economics remain fictional game tuning, not measured Vermont county statistics, property appraisals or Vermont tax law. Existing county indices are retained and new counties use synthetic profiles. Cross-county travel and coverage retain the existing high-level rules, not a road network or mileage model. Adding counties changes future market opportunities and economy draws; reproducibility is preserved within this version, not promised against an older version with only three regions.

Validation: the full pytest suite passed, 436 tests in 266.40 seconds, with two pre-existing dependency deprecation warnings. This includes five new Vermont tests for county opportunities, migration, backups, filters and seeded daily/save-load equivalence. A read-only SQLite backup of the current campaign migrated in an isolated QA folder: all account balances, ownership, names, employee identities and random states were preserved. Eight pages rendered, journal reconciliation passed, and reopening made no additional migration. Browser QA verified Vermont branding and using the county selector to show only Grand Isle County properties and development lots. The dropdown layout was visually inspected.

Restart the game launcher/server to load 0.24.0; each saved campaign migrates on open. Next potential geography work is optional county-specific economic tuning and travel distances; neither is required to use the county setting.
