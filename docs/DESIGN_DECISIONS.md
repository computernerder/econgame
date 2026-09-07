# Design decisions

These decisions reflect the user's answers on 5 September 2026 and take precedence over proposed defaults in Empire_Manager_Comprehensive_Handoff.docx. That document remains the comprehensive roadmap.

## D001 Real estate can stand alone

The player can pursue property flipping or rentals without ever running another business. Property buying, purchased improvements, renting and selling move into the first playable milestone. This changes the original M1 retail-first order, not the eventual employee/business scope.

## D002 Forgiving default

The default campaign should allow recovery, visible growth and experimentation. The first scenario uses $350,000 of personal capital, favorable purchase opportunities, predictable holding costs, no mandatory debt and no forced bankruptcy ending. These numbers are initial tuning values.

## D003 Renovations are purchased work

Initially, the owner pays contractors and waits for completion. Later, owners may use their own demonstrated skills to reduce money costs in exchange for personal time. First-version renovations capitalize their cost and increase condition after a known duration. They do not operate while occupied.

## D004 Visible employee information with unknown undeveloped skills

Degrees and demonstrated skills are visible immediately. Relevant skill that has not been demonstrated remains unknown, rather than being treated as zero. An electrical engineering graduate working as a cashier has a visible degree and unproven specific engineering skills. Preserve this when the employee milestone begins.

## D005 Personal owner and multiple success measures

The player is a personal owner. Personal and company funds are separate. Personal wealth includes owned company equity once; it must never double-count the same assets. Business wealth, business size, culture, morale and other outcomes have independent measures instead of a single compulsory score. First version shows property and wealth measures; employee measures wait for actual employee systems.

## D006 Aging and optional future succession

The owner ages with the calendar. Succession is an optional later feature. Aging does not force a campaign to end in the current version.

## D007 First implementation gate

Deliver a local desktop window with real property transactions, purchased work, leases, sale closing, daily time, separate capital accounts, a double-entry journal, resumable SQLite saves and actionable pauses. This combines foundational M0 work with a property-focused first playable slice. Full M0 (including distribution benchmarks) and the handoff's retail/employee M1 are not claimed complete.

## D008 Presentation baseline

Use Python, FastAPI, Jinja server-rendered HTML, CSS, SQLite and pywebview. A small local JavaScript file handles commands, native dialogs and progress polling; HTMX is not needed yet because there are no fragment-update screens. This refines the proposed baseline and avoids shipping an unused dependency. Browser development and desktop use the same interface and engine.

## D009 First-version simplifications

Cash purchases close immediately. Contractor work takes days. Buyers agree to 98% of the current estimate, pay at closing after 7–14 days and incur a 3% selling cost. Tenant search takes 3–7 days; leases last one calendar year at suggested rent. Rent and holding costs are allocated by calendar day and settled daily. Occupied assets cannot be sold or renovated until lease expiry. No mortgage, tax engine, depreciation, tenant default, owner time budget or market-price drift is implemented yet.

## D010 Save compatibility

Schema, simulation and content versions are explicit. Unsupported versions are rejected; no migration is invented before there is an older supported game schema. Future migrations must create backups and be tested transactionally. The current schema is version 1. A one-writer process lock protects each campaign and each day commits atomically with its journal and events.


## D011 Businesses and people milestone (0.3)

Acquire whole companies with stable person, position, employment and property identities. A three-day escrow closing transfers disclosed cash, inventory, equipment and properties with no inherited debt. Purchase premiums are parent-held goodwill; reciprocal ownership stakes and capital eliminate from group wealth. Subsidiaries can acquire companies and properties using their own accounts. Company ownership, employee reporting and premises occupancy remain separate relations.

Retail sales consume stock; restaurant meals require simultaneous kitchen/service capacity and incur ingredient waste. Engineering earns support, hourly and fixed-fee work across a finite qualified time budget; earned work, invoices and collections are separate ledger transitions. Property managers service external units; rental companies earn from actual owned leases. A larger mixed retailer includes occupied premises and a rental apartment. Economic parameters are fictional tuning values.

Named people have visible qualifications and demonstrated skills. Five worked days in a new role or completed training reveal its skill. Employee actions cover hiring, terms, training, leave and ending employment with retained history. Salary/benefits accrue daily, paid Friday; coverage depends on schedule, leave, training, skills, engagement and burnout. Benefits/pay/management/workload affect morale; culture remains an explicitly labeled morale proxy. No automatic resignation, succession, tax, full-world labor market or 10,000-person scalability claim is made.

## D012 Version-1 migration

Schema and simulation version 2 retain version-1 property mechanics and add business data. A recognized older save gets a unique SQLite backup before migration. Its account balances, original journal, property state and property RNG remain unchanged. New catalogs use an independent seeded RNG. The new snapshot, migration event and version flag commit together. Failed migration leaves the original file unchanged. Unknown content/schema versions remain rejected. These decisions supersede the version-1-only wording of D010.


## D013 Empire development release (0.4)

The schema-3 expansion includes the fictional workforce, economy, tax, debt, property-space and franchise systems that supersede earlier missing-feature lists in D009/D011. Recognized schema-1 and schema-2 campaigns receive unique backups before migration. Release validation uses isolated save copies. New campaign creation preserves previous save files and remembers the new file in last-campaign.txt. Existing mode defaults and optional personal succession remain in force. Scope and remaining validation are tracked in FULL_GAME_STATUS.md; the release is not a full-handoff completion claim.


## D014 Business premises and rent counterparties (0.4.1)

Companies can purchase property with their own funds and explicitly occupy a vacant building in their region. Whole-building assignment is a simplified game use decision. If another controlled owner holds the building, a premises lease moves deposits and rent to that owner's ledger. Individual expenses and income are retained; consolidation eliminates internal flows. Default external rent has a named non-player landlord and mirrored receivables. New arrears settle after funding even if a lease has ended. Historical journal entries are preserved rather than inventing retroactive recipients. The business page shows the actual premises, recipient and monthly rent.


## D015 Engineering job automation (0.4.2)

Engineering businesses default to automatic job acceptance; the owner can opt into manual acceptance. Completed jobs create one invoice and continue without a routine pause when automated. New work starts on the next staffed working day. Quotes use a separate deterministic seed based on business identity and job number, preserving other random streams and preventing quote rerolls on refresh. Size ranges from 75% to 150% of the baseline effort and fee per work hour ranges from 90% to 115% of its baseline. Active contract terms do not change. Qualified work capacity is shared with existing support/advisory commitments, fee is earned proportionally, and completed invoices collect after 14 days. Current project terms and progress survive older-save loading; new fields have compatible defaults.


## D016 Staffing guidance and guided offers (0.4.3)

Business pages distinguish hard opening-role requirements from workload-derived planning hours and optional support roles. Opening rules and the guide share one authoritative role mapping. Incoming hires and net shared assignments reduce planned shortages. Separate five-weekday estimates reuse hourly work-capacity logic on isolated copies so schedule overlap, leave and qualifications remain meaningful. Engineering uses an explicit 20-working-day project planning target; it is not a mandatory staffing gate. Guided hiring preserves hidden skills, filters known eligibility restrictions, rechecks on submission, and creates/reuses the position atomically with the accepted offer. The one-time recruitment fee and recurring wages, benefits and payroll tax are reviewed before commitment. Saves need no schema change.


## 6 September 2026 — operating systems extension

The latest user design replaces the earlier no-ending default with actual personal/holding-parent insolvency. Optional locations use separate operating books inside one legal company, sharing obligations and income-tax assessment; separately formed subsidiaries retain isolation. Service and repair work consumes scheduled staff capacity. Existing fixed-fee manufacturing orders survive the manufacturing inventory model. Property ownership transfers include leases/deposits/receivables without transferring tenant businesses. Systems version 2 prevents an older engine from silently ignoring these new obligations. See OPERATIONS_RELEASE_011.md for scope and explicit later features.

## 6 September 2026 — service projects and tenant requests

Service products extend the existing queue rather than adding permanent department unlocks. HR assessments and succession plans retain uncertainty and stable employee IDs. Onboarding consumes both provider and participant time. IT deployment effects depend on maintained system condition and actual labor/demand. Tenant requests are observations of existing occupied-property systems; repair bookings consume real resources and do not immediately resolve complaints. Overdue unresolved requests affect renewal negotiations. Systems version 3 prevents an older engine from treating specific projects as generic department effects. See SERVICE_PROJECTS_012.md for delivered behavior and remaining scope.

## 6 September 2026 — commercial contracts

New Covenant Works listings publish fictional transfer restrictions and existing roof-work obligations before legal review. Consent and negotiated fees are buyer-specific; failed negotiations cannot be rerolled. The initial purchaser retains the disclosed covenant, with actual condition checks, reserved work budgets and dated breach payables. Ordinary property purchases retain their existing rules. Outside-service agreements prepay finite, shared daily capacity; unused credit can expire, while cancellation cannot convert nonrefundable credit to cash. Systems version 4 protects the new commitments from older engines. See COMMERCIAL_CONTRACTS_013.md for exact accounting and deferred scope.

## 6 September 2026 — property service companies

Cleaning, landscaping and security use qualified worker pools, equipment limits, immediate supply costs and delayed outside invoices. Prepaid property plans share those pools, including travel, and release internal payments only as work occurs. Consolidation removes reciprocal internal income and expense. Property presentation and recent patrols change actual rental offers, renewal ceilings and property incident risk; they do not repair structural systems. Whole plans require authority and affordability, and ownership changes cancel undelivered commitments. Systems version 5 and a new content hash prevent older engines from overlooking the new industries and reserves. See PROPERTY_SERVICES_014.md for delivery, recovery, accounting and deferred scope.
