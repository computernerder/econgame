# Staffing guide validation (0.4.3)

The full regression passed 78 tests in 39.83 seconds. Following final applicant ordering, live-cost UI changes and the shared-staff case, all eight staffing-guide tests passed. Coverage includes startup opening roles and workload targets, read-only projections, engineering qualifications, custom license checks, conflicting restaurant shifts, incoming hires, atomic vacancy creation/reuse, failed offers, cost previews, and shared assignments reducing the target gap. Two existing upstream test-client deprecation warnings remain.

An isolated browser campaign displayed the retail guide and guided cashier offer. Changing hours from 4 to 20 updated salary from $260 to $1,300 and minimum funding to $1,600. The review showed $1,503 estimated monthly employer cost ($1,300 wages, $125 benefits, $78 payroll tax) and a $300 immediate recruitment charge. Confirming created a joining employee and the recomputed plan showed the gap closed. The final client returns successful guided hires directly to the business page. The guide layout was visually checked. No user campaign hires were performed.

Coverage estimates use copies of saved state and the existing hourly work-capacity calculation, with current abilities and commitments held fixed. They are not a full economic forecast or a guarantee of demand fulfillment.

---

# Engineering automation validation (0.4.2)

Full regression: 71 tests passed in 40.12 seconds, with two existing upstream test-client deprecation warnings. Engineering checks cover automatic successive jobs over 100 days, distinct stable quotes, exactly one invoice per completed job, earned-fee reconciliation, no routine completion pause in automatic mode, manual acceptance, immutable active terms, read-only previews/quotes, persisted settings, legacy defaults, and the effect of fee and work-budget changes on identical daily capacity.

An isolated browser campaign completed its initial $27,000 / 180-hour job and automatically accepted a $23,085 / 135-hour job. The page showed remaining hours, earned fee, contract value per hour, next-job quote and the earlier invoice awaiting its due date. The layout and default-enabled automatic control were inspected. No test actions were applied to the user's campaign.

---

# Business premises validation (0.4.1)

The full regression passed 66 tests before the final additional external-arrears case. After the final changes, the 16 premises and campaign-product tests passed. Seven premises tests now cover company-funded purchase and owner occupation; holding-company rent receipt and group elimination; named external landlord receipts; settlement of unpaid external rent after relocation; internal arrears after lease termination; duplicate occupancy/unauthorized purchases; and rendered landlord controls. Two existing test-client deprecation warnings remain.

An isolated browser campaign completed the whole-building lease review and confirmation. The review showed equal and opposite deposit cash movements; the business page displayed the selected property, holding-company landlord and actual monthly rent. Layout was visually checked. No test actions were applied to the user's campaign.

---

# Empire development validation (0.4)

6 September 2026. The release regression has 60 passing tests, with two existing upstream test-client deprecation warnings.

New product checks cover every campaign page under personal and company ownership; read-only views; repeatable forecasts with live/save isolation; blocked forecasts during advancement; balanced Guided, Entrepreneur and Sandbox starts; separate-save creation and command retries; dollar conversion; lease deposits/termination; and initial franchise rendering and royalty accounting.

`tools/verify_release.py` copied the actual schema-2 campaign using SQLite's backup API and a read-only source connection. Migration preserved all existing accounts, the property random stream, journal and date, and created one pre-v3 backup. The migrated copy advanced 365 days from 2027-06-17 to 2028-06-16 in 14.38 seconds with daily SQLite commits, then passed the ledger audit. This is a small existing-campaign smoke check, not a large-workforce benchmark. No test actions were applied to the user's campaign.

An isolated browser save was used to inspect the business-development layout, calculate and display a 30-day forecast, and complete the reviewed separate-campaign creation flow with a visible success message. The desktop shell itself was not requalified in this release; it retains the existing WebView2 launcher.

The previous validation reports below are historical. Their missing-feature lists describe those earlier versions, not 0.4.

---

# Business and employee update validation (0.3)

5 September 2026. Staging regression: **39 passed** in 20.81 seconds, with the same two upstream test-client deprecation warnings. Tests include all five revenue models, cash-funded acquisition/closing, stable staff identity, included premises/rentals, nested ownership, property purchases by companies, stock consumption, nonoverlapping restaurant shifts, missing cashier coverage, engineering accrual/invoicing/collection, Friday payroll, hiring delay, training and leave, hidden engineering skills, invalid whole-number inputs, consolidated dividend elimination, rolling decision costs, read-only previews and all new screens.

A copy of the actual version-1 campaign migrated successfully with identical existing account balances, journal, date, property fields and property RNG. Reopening did not repeat migration. An injected migration failure left the original file byte-for-byte unchanged.

An isolated browser campaign completed an acquisition, paused on closing with all three staff transferred, disabled automatic restocking through a reviewed policy form, and changed a cashier salary from $2,600 to $2,800 with an employer-payroll preview. Marketplace and employee layouts were visually inspected. No test purchases were made in the user campaign.

Current limits: source distribution uses the existing Python environment and WebView2. No standalone installer, financing, tax, depreciation, whole-business sale, succession, automated resignation, rich culture model or large-workforce performance guarantee. Daily store/service opening is weekdays; operating buildings cannot yet be repurposed.

The earlier 0.2 checks below are historical, not performance measurements or limitations of the new business systems.

---

# First playable validation

Executed on 5 September 2026 on Windows 11 build 26200, Python 3.12.14, AMD64 Family 25 Model 97 Stepping 2, 12 logical CPUs.

## Automated regression

`python -m pytest -q`: 18 passed both in staging and in the installed project (final installed run: 12.69 seconds). A dedicated per-run temporary directory avoids a Windows permission collision between sandboxed and normal test runners. The suite covers:

- Seeded world generation, month-end clamping and leap-year day allocation.
- Atomic failure for unaffordable transactions.
- Separate personal/company accounts, capital returns and no wealth double-counting.
- Buying, capitalized renovations, delayed sale closing, fees and realized profit.
- No rent before move-in, lease constraints, withdrawal and lease expiry.
- A background year versus the same 365 daily transitions, with save/reload partway through.
- Duplicate command retries after reload, changed payload rejection and stale revisions.
- Pausing on completed work and cancellation after a valid daily commit.
- SQLite rollback when a duplicate journal source fails.
- Recoverable backup, unsupported schema rejection and one-process-per-save locking.
- Origin, session, host, stale command, text escaping and static path checks.
- Exact February rent in a leap year and correct owner age.
- Unpaid holding costs without negative cash; settlement after additional capital.
- Random-state continuity for tenant search and tenant identity.
- Invalid money inputs, including non-finite values and excess precision.

Two upstream deprecation warnings remain in FastAPI/Starlette's test-client integration with httpx/AnyIO. Tests pass and `pip check` reports no broken requirements. They do not affect the game interface.

## Browser playthrough

Used an isolated temporary campaign, separate from the user's eventual save. Visually inspected the overview and property market, and exercised the visible purchase, renovation, time advance and rental controls.

Purchased 101 Willow Lane for $80,784 including closing costs. Booked a $2,310 interior refresh. A month skip stopped on 16 January after 15 days; condition increased from 50 to 65 and estimated value from $88,000 to $94,600. The rent offer increased to $1,032 per month. A tenant moved in on 23 January with a lease ending 23 January 2027. The financial report showed $33.29 earned rent, $99.40 holding costs and a $66.11 realized loss to date, with $83,094 held as the property's cost basis.

No browser error/warning logs were reported in this playthrough. Inspected the normal desktop viewport, the 850×650 minimum desktop layout and a 390×844 narrow layout. The narrow layout has no document-wide horizontal overflow; its navigation scrolls horizontally.

## Native Windows test

The pywebview/Edge WebView2 window rendered the actual game. Tested Advance time → One day through the native controls and observed the saved date change from 1 January to 2 January 2026.

Initial desktop startup failed with Python.NET 3.1.0 and clr-loader 0.3.1. Pinning Python.NET 3.0.5 and clr-loader 0.2.9 resolved the observed launch failure on this PC. Both the project metadata and full lockfile preserve the tested combination. The console-free launcher also needed explicit log streams and disabled console color detection; Uvicorn initialization with no stdout/stderr was verified after that fix. This is an observed compatibility result, not a diagnosis of all possible runtime failures.

The installed `Play Empire Manager.cmd` launcher was then verified using console-free `pythonw.exe`. The user-played preview was preserved via SQLite backup, audited and resumed in the installed game at 29 March 2026, revision 100, with two owned properties and $186,662.93 personal cash. The recovery copy is `saves/preview-recovery.sqlite3`; the active save is `saves/campaign.sqlite3`.

## Small benchmark

`python tools/benchmark.py` ran seed 42, three owned properties with tenant searches, no employees and 365 daily SQLite commits. The benchmark intentionally continued through property events to measure the same daily pipeline.

- Simulated year: 3.180 seconds.
- Read-model p50: 0.073 milliseconds.
- Read-model p95: 0.095 milliseconds.
- Save size: 753,664 bytes.
- Complete journal-to-balance audit: passed.

This does not establish the handoff's 100-employee or 10,000-employee performance targets, which are not applicable until those systems exist. Peak memory, installer size and clean-PC deployment have not been benchmarked.

## Remaining limits

This is the property-focused first playable slice, not the full comprehensive handoff. It does not implement retail operations, employee management, taxes, mortgages, succession, tenant defaults or variable market prices. It uses daily cash rent settlements and treats purchased renovations as capital improvements. Selling and renovating occupied properties must wait for lease expiry.

Schema version 1 rejects unsupported versions; there is no older supported schema needing a migration yet. A standalone installer, bundled Python and automatic WebView2 installation remain future distribution work. The source launcher uses the configured virtual environment and the already installed Windows WebView2 runtime. Local assets and application code have no runtime network dependency; a physically disconnected-machine installation test has not been performed.

## Installed 0.3 verification

The installed project passed all 39 tests in 21.99 seconds (two known upstream deprecation warnings). Portable generated legacy fixtures also passed when the local campaign-copy fixture was absent. The current user save migrated to revision 101 without advancing its 29 March 2026 date, retaining $186,662.93 personal cash, two properties, $193,650 estimated property value, $1,128 monthly rent and $1,002.03 realized profit. The pre-migration save is `saves/campaign.before-v2-595bf52db627.sqlite3`; prior source files are in `backups/source-before-v03-20260905-195018.zip`.

The console-free native launcher reopened version 0.3 from the project folder. Its rendered interface showed the preserved campaign figures and the new Buy a business, My businesses, People and Organization navigation. No gameplay decisions or time advancement were performed in the migrated user campaign.


## 0.10.0 design increment 1 — 6 September 2026

Implemented authority contracts and a conservative cash commitment forecast. New coverage includes business/geographic scope, parent permissions, cumulative month spending across dates and contract edits, prospective cash rejection without ledger mutation, incoming payroll, refundable deposits, receivables excluded from liquidity, project limits/acceptance, headcount/objectives, automatic-stock checks, underestimated director costs, required-stop thresholds, request deferral, scheduled loan principal, shared-service forecast allocation, UI commands/persistence, deterministic four-day replay with a midpoint SQLite reload, and covering-manager authority when a director is absent.

Executed in the isolated `C:/Projects/LearnPython/empire-authority` source tree with the project's Python environment:

- Initial existing leadership/management/skip regression: 30 passed.
- First full `python -B -m pytest -q`: 190 passed in 96.33 seconds.
- Expanded authority, leadership, management, template and skip regression: 52 passed in 13.63 seconds.
- Second full `python -B -m pytest -q`: 195 passed in 98.97 seconds. The final covering-manager guard and its additional test were then covered by the targeted run below.
- Latest targeted authority and engineering-job regression: 25 passed in 12.46 seconds, including the final absent-director guard.
- One attempted targeted command named nonexistent `test_engineering.py`; pytest ran no tests. Corrected to `test_engineering_jobs.py` above.
- Starlette/httpx and AnyIO deprecation warnings are existing dependency warnings.

An isolated SQLite backup of the live campaign loaded and passed Store.audit at 2028-04-08. The 0.10.0 browser preview displayed the actual Management overview and expanded commitment/form panels without rendering errors or overlap at the available desktop viewport. Northbank Engineering's displayed values came from its saved balances and obligations; no hard-coded dashboard totals were introduced. Only the disposable copy was opened in the preview server. Live save files were not edited.

Limitations and remaining acceptance gates are in DESIGN_UPGRADE_PLAN.md. No distress/closure, department queue, factual legal negotiation, detailed repair, flip downside, VP or large-scale performance claim is made for this increment.

## 0.11.0 operating simulation release — 6 September 2026

The current behavior, stages, financial interpretation and explicit remaining scope are documented in OPERATIONS_RELEASE_011.md. Earlier sections above describe historical releases and retain their original limitations for context.

Executed using the existing project's Python environment against the isolated `C:/Projects/LearnPython/empire-completion` source tree:

- Final full regression before the last property presentation refinement: **227 passed in 108.02 seconds**, with two existing Starlette/httpx and AnyIO deprecation warnings.
- Previous focused authority, completion, expansion-finance and owned-bank loan regression: **62 passed in 20.18 seconds**.
- After the final property quote/display and action-order refinements: **45 passed in 15.70 seconds** across completion systems, campaign UI and property categories.
- Earlier full runs caught factory-order compatibility and a stale template version guard; both were corrected before the final passing run. Mistyped targeted test paths ran no tests and were corrected.

New acceptance coverage includes obligation aging and FIFO settlement, subsidiary isolation and closure, parent insolvency, finite bank capital, service overload and prepaid/mixed refunds, factual legal refusals and collections, resource-consuming repairs and callbacks, profitable and loss-making flips, occupied property sales without acquiring tenants, internal construction and service reconciliation, cumulative future authority commitments, legal-company location obligations and a single tax assessment, executive employee identity/time, outsourcing unfinished work, delayed liquidation losses, and a 12-day deterministic replay with a midpoint save/load. Existing single-business, employee identity, engineering-job, authority, skip, UI and financial tests remain in the full suite.

A read-only SQLite backup of the live campaign loaded and audited at **2028-04-08**, retaining personal cash **$65,266.73**. The disposable copy advanced 20 days and audited again. Its operations upgrade retained balances, employees and date, added office/mixed-use opportunities, and created a pre-upgrade backup. Migration idempotence and preservation are also covered by an automated test. Testing never opened the live campaign through the new Store or advanced its date.

Browser validation used only this disposable copy. Operations, Home office services and Property workbench rendered version 0.11.0 with the persistent cash header and visible action controls at the available desktop viewport. An outsourced accounting request charged **$720** upfront, delivered **240 minutes on each of two days**, and completed on **2028-04-30** with a real ledger report and recorded outside expense. The service queue showed remaining effort and completion. The report is a dated work product captured when prepared; later daily postings can change current cash. Final property controls were reordered to show inspection and budgeting before acquisition, and repair duration/benefit displays now derive from the simulation quote.

These checks do not establish decades-long balance, large-workforce performance, a clean-PC installer, or the explicit later district-development and deeper specialist-service scope. See OPERATIONS_RELEASE_011.md for those limits and the next development gate.

### Installed release verification

Installed 45 reviewed files into `C:/Projects/EconmicSimulationGame`, verifying every file hash and checking for intervening source edits before copying. Source backup: `backups/source-before-operations-20260906-052020.zip`. The installer excluded saves and test campaigns.

The installed modules reported **0.11.0**. Six installed screens rendered successfully against a fresh disposable backup: Operations, Home office, Property workbench, Organization, Management and the engineering business. The installed workbench places inspection before acquisition. The copy upgrade created a recovery backup and preserved all existing account balances, employment records, positions and the simulation date. The live campaign still had older content migrations pending; those also added seller staff for newly available market businesses, without changing existing employees. The verification initially assumed the total employment count would be unchanged, then was corrected to verify every existing identity and field and restrict additions to seller records.

Both the freshly migrated copy and the browser playthrough copy passed journal/balance and simulation validation. The actual live SQLite world was read again and was unchanged: **2028-04-08**, personal cash **$65,266.73**. Restarting the installed game will load the release and migrate the real campaign with its own automatic backup. A console-free native-window restart was not executed during this release verification.

## 0.12.0 specific service projects — 6 September 2026

Read the live code, extracted handoff, release notes and historical gap inventory before extending the queue. Implementation was staged at `C:/Projects/LearnPython/empire-service-projects`; the live campaign was never used for gameplay tests. See SERVICE_PROJECTS_012.md for behavior and explicit limitations.

- Initial completion/authority/campaign regression: **61 passed in 20.15 seconds**.
- New workflow tests initially caught departed-employee onboarding incorrectly calling an active-employment lookup; corrected to close the delivered task with an unsuccessful outcome and retain its costs. A replay assertion was normalized for JSON list/tuple representation of identical RNG state. An authority test was corrected to run on a scheduled manager day.
- New workflow regression after these fixes: **16 passed in 4.81 seconds**.
- Full regression: **243 passed in 115.18 seconds**, with the two existing upstream deprecation warnings.
- After explicit manager IT-support and tenant-deadline skip coverage: **27 passed in 10.70 seconds** across service projects and campaign UI. The final queue labels also distinguish specific products, expenses and unused prepayments.
- Final targeted rerun after the queue-label refinement: **27 passed in 10.79 seconds**.

Acceptance includes real recruiting/offer constraints, uncertain assessment, paid onboarding and leave/exit behavior, cancellation refunds, stable succession identities without automatic promotions, deployed-system wear/support, demand-derived inventory targets, wrong-recipient rejection, factual tenant requests, resource-consuming repair resolution, renewal concessions, cumulative service commitments, property-owner scope enforcement, finite internal employee pools, promotion licenses, automatic authorized IT support, mandatory repair-deadline interruption, deterministic nine-day daily/reload equivalence and migration backup/idempotence.

A disposable SQLite backup of the user's campaign migrated to systems version 3 and audited at 2028-04-08, preserving existing employees, account balances and personal cash $65,266.73. Browser preview displayed the named HR/IT forms. A succession review for Willow Corner Market correctly previewed and charged $1,440 against that business, not the personal account. A requested week skip stopped after two days on an existing owner-approval exception, with 480 of 960 provider minutes delivered and $720 recognized as outside expense. No blocked decision was approved to force the skip through.

Two explicit one-day steps completed the queued review on **2028-04-12**. It recorded 960 delivered provider minutes, $1,440 actual outside expense, zero remaining prepayment, and a two-person shortlist retaining Morgan Ellis and Taylor Brooks in their original jobs. The browser's desktop layout retained the cash header without overlap. After closing the preview server, journal and simulation audits passed; five fresh application screens rendered the final labels. The real campaign was read again and remained unchanged at 2028-04-08 and $65,266.73 personal cash.

## 6 September 2026 — contracts and purchasing (0.13.0)

Continued from the live code, previous release and preserved design handoff in `C:/Projects/LearnPython/empire-commercial-contracts`. See COMMERCIAL_CONTRACTS_013.md for delivered behavior and limits.

- Initial inherited completion/service/property regression: **54 passed in 15.40 seconds**.
- First commercial workflow regression: **63 passed in 17.09 seconds**.
- Full regression after the initial 15 new tests: **260 passed in 119.77 seconds**.
- Added specialist/mixed-delivery and small-repair commitment regressions. The first test setup incorrectly assigned the computed `Property.value`; corrected to set its underlying full value. Final authority/navigation/commercial regression: **42 passed in 12.39 seconds**.
- Full regression with all 17 commercial tests: **262 passed in 121.04 seconds**. Two existing Starlette/httpx and AnyIO deprecation warnings remain.
- After exposing the saved repair estimate in the legal result and clarifying purchasing guidance: **17 passed in 4.59 seconds**.

Coverage includes disclosures preceding paid review, buyer-specific consent, actual negotiated future fees, counterparty refusal, specialist escalation, repair reserves, preventive-work evasion prevention, one-time dated breach payables, full prepaid affordability, account scope, real discounted delivery, shared supplier capacity and priority, zero-capacity deadline alerts, credit expiry and cancellation without cash creation, deterministic daily/reload equivalence, read-only screens and migration backup/idempotence.

A disposable SQLite backup of the real campaign migrated and audited at **2028-04-08**, retaining accounts, personal cash **$65,266.73**, and every existing employee field. The browser exposed disclosures and reviewed a **$1,080** personal purchasing work order. Three one-day steps delivered 720 provider minutes and produced three supplier responses on **2028-04-11**; existing owner-approval pauses remained visible. The preview purchase correctly charged **$1,740** for 1,200 minutes and recorded an equal service-credit asset, a shared daily limit of 120 minutes, and expiry on **2028-06-10**. No actual campaign transaction was executed.

Browser layout inspection confirmed the fixed cash header, readable actions and disclosure table. Final verification reopens the disposable save, audits its journal and simulation, renders seven screens with the installed engine, checks installed source hashes, and compares the complete live campaign JSON with the original read-only snapshot. Remaining product gates are documented in COMMERCIAL_CONTRACTS_013.md; this is not a claim that every original design milestone is complete.

## 6 September 2026 — property service businesses (0.14.0)

Read the installed code, HANDOFF_TEXT.txt and release/design inventory before extending the simulation in `C:/Projects/LearnPython/empire-property-services`. Existing comments and historical handoff remain preserved. See PROPERTY_SERVICES_014.md for implemented behavior and explicit limits.

- Initial commercial/operations regression: **48 passed in 13.97 seconds**.
- New property-service tests initially exposed an underfunded test fixture and assumptions that internal work must displace outside work even when spare capacity existed. Funded the property through the normal command and exercised a workload that actually exceeds available capacity. Final focused run: **16 passed in 6.10 seconds**.
- Full regression: **278 passed in 141.86 seconds**.
- Added ordinary-home rent integration and explicit manager-approval coverage; leadership/service/operations regression: **79 passed in 24.67 seconds**.
- Final full regression: **280 passed in 145.37 seconds**, with the two existing Starlette/httpx and AnyIO deprecation warnings.
- After guard-credential recovery controls and current-owner property ordering: **18 passed in 7.07 seconds**.
- After connecting local equipment improvements to the service equipment ceiling: **19 passed in 7.22 seconds**, including a check that equipment cannot create worker hours.

Coverage includes acquisition and startup of all three industries, staffing guidance, delayed outside income and actual supplies, no-HQ personal service plans, completion-dependent effects, internal/external capacity competition, priority, supply-cash exhaustion, refunds, ownership/provider changes, duplicate/wrong-provider rejection, security license enforcement and renewal, weather, expiring patrol coverage, deadlines, repeated-day delivery protection, cumulative delegated commitment limits, required approvals, read-only views, migration backups, daily/reload equivalence and financial reconciliation. Completed care expense is included in the property's project-cost totals.

A separate seed-42, 90-day operating sample validated each daily state without injecting business cash after acquisition. Cleaning remained operating with **$57,732.10 cash and $15,244.17 profit**; landscaping remained operating with **$37,709.13 cash and a $1,886.34 loss** during the winter sample; security remained operating with **$77,407.02 cash and $34,123.75 profit**. Receivables remained distinct from cash. This is a bounded behavior check, not multi-seed or decades-long balance certification.

A disposable SQLite backup of the user's save migrated to systems version 5 at **2028-04-08**, preserving accounts, personal cash **$65,266.73**, and every existing employment field. In the browser, a personal cleaning visit for 101 Willow Lane previewed and reserved **$144** with no immediate care benefit. Sunday left it queued; Monday **2028-04-10** completed 120 qualified minutes, recognized $144 expense, reduced its reserve to zero and raised cleanliness to 94/100. Existing owner-approval stops remained visible. The fixed cash header and care table rendered without overlap. Only the disposable campaign was advanced.

Release verification reopens the QA save, audits journal and simulation, renders eight management pages and three new industry listings, checks installed file hashes, and compares the full live-save JSON to its original read-only snapshot. Hotels, parking and the district-development sequence remain explicit later work.

The first preinstallation comparison detected that the live save had acquired the installed 0.13 migration records during this work (revision 1003 to 1010, systems 1 to 4). Its date, account balances and personal cash were unchanged. No installation had yet occurred and all gameplay checks used disposable copies. A fresh read-only backup of this latest live state was then migrated and audited separately. Installation verification compares against that preinstallation snapshot rather than treating the older snapshot as current or replacing the player's save.

By the fresh backup, the live campaign had advanced to **2028-04-10** with **$65,319.05 personal cash**. That latest copy migrated from systems 4 to 5 with all current accounts and existing employment fields preserved. The staged 11-page verification and ledger audit passed against this latest preinstallation baseline.
