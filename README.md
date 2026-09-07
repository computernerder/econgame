# econgame — Empire Manager

A local business and real-estate simulation set in Vermont. Manage one business, a property portfolio, or a group of companies with employees, delegated leadership, shared services and separate financial accounts.

Current source version: **0.34.0**. Repository: [computernerder/econgame](https://github.com/computernerder/econgame), using SSH remote `git@github.com:computernerder/econgame.git`.

## Docker and Unraid

The game now has a headless network server with sign-in, persistent campaigns and graceful shutdown. Follow [Docker and Unraid deployment](docs/DOCKER_UNRAID_034.md) for the server at `192.168.1.3`, appdata permissions, access keys, updates and importing desktop saves.

For a local Docker test, run `docker compose up -d --build`, then open `http://localhost:8892`. Retrieve the generated sign-in key with `docker compose exec econgame cat /data/access-key`. For other computers to connect, set `EMPIRE_PUBLIC_URL` to the exact LAN address in `.env` before starting; `.env.example` supplies the Unraid settings.

Each container serves one shared game library and one active campaign. Existing revision checks prevent stale decisions from overwriting newer work. Separate containers and data volumes provide independent game libraries. Desktop play remains available below.

## Set up a new checkout

Use Python 3.11 or newer (validated locally with Python 3.12 on Windows). The Windows desktop interface also uses Microsoft Edge WebView2.

```powershell
git clone git@github.com:computernerder/econgame.git EconmicSimulationGame
cd EconmicSimulationGame
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m economic_simulation
```

After setup, **Play Empire Manager.cmd** launches the desktop game. For browser development, run `.\.venv\Scripts\python.exe -m economic_simulation --browser` and open the local launch URL printed by the server. Use `--save PATH` for an isolated test campaign.

Campaigns in `saves/`, source backups, virtual environments and temporary QA output stay local and are excluded from Git. Updating source does not transfer campaign progress to another computer. Close the game before updating with `git pull --ff-only`, then restart it. Keep a separate backup of your saves.

## Development and handoff

Run `.\.venv\Scripts\python.exe -m pytest -q` from the repository root. Tests use isolated temporary campaigns. The Windows test configuration creates a fresh `empire-manager-tests-*` directory per run; remove your completed test run's directory when it is no longer needed. An explicit `--basetemp` can keep QA data in a known disposable location; pytest clears that location at the beginning of a run, so never point it at a real campaign or source directory.

Read [the handoff](docs/HANDOFF_TEXT.txt) and the latest increment notes before changing the simulation. Preserve seeded outcomes, daily-step/time-skip equivalence, save compatibility, employee identities and ledger reconciliation. The older release notes below describe the project's development history.

Navigation usability (0.33.8): switching companies keeps the current tool open, section highlights match the current page, and missing or inactive detail links lead to an explained directory view. Mobile navigation keeps all destinations and the decision count accessible; keyboard users can skip navigation and follow task links with visible focus. See [validation and limits](docs/NAVIGATION_USABILITY_0338.md). Restart after updating.

Quieter time skips (0.33.7): routine completions stay in the activity log by default and financial events below $1,000 do not interrupt. Advance time now includes interruption preferences and a quieter preset. Handled manager issues and closed decisions do not re-pause. Interrupted target dates persist and Resume rechecks all approvals; a recovery day preserves the original target. Required approvals, unpaid payroll, reserves and failure still stop time. Explicit existing settings remain respected. See docs/QUIETER_SKIPS_0337.md for validation and limits. Restart after installation.

Restaurant growth (0.33.6): enable meal-time operations from an owned restaurant business page. Opening days/hours, demand, stock, kitchen/dining layouts and real shift coverage support a larger single-location team. Prep cooks, dishwashers and hosts consume real time; managers fill workload gaps within headcount/cash/authority limits and stagger unpinned shifts. Search/filter the weekly roster, edit days/start times, see employer costs and seven-day coverage. Existing saves keep the prior restaurant model until a plan is saved. See docs/RESTAURANT_SCALE_0336.md for validation and limits. Restart after installation.

Shared resources (0.33.5): Home Office team cards show named staff, coverage, assignments, jobs and direct task actions. Schedule regular support creates a staff agreement and an existing-shift reservation in one review; real hours, costs, leave, credentials and separate company books remain. Internal recruiting/IT/agent/repair links select the chosen provider and relevant fields. See docs/SHARED_RESOURCES_0335.md for validation and limits. Restart after installation.

Internal property specialists (0.33.4): managers and directors prefer qualified home-office maintenance staff and licensed real estate agents, then other owned providers. Repairs, basic cleaning and grounds care consume shared employee time and actual resources. Closing preparation must finish before reduced brokerage applies. A per-business preference permits outside providers; scope, workload and financial limits remain enforced. See docs/INTERNAL_PROPERTY_SERVICES_0334.md for validation and limits. Restart after installation.

Manager property coverage (0.33.3): default manager/director geography includes properties owned by the businesses they oversee. Previously blocked routine care returns to the manager queue when current scope, funding and workload permit, then executes on time advance with real costs and an audit entry. Explicit restrictions and deferrals remain binding. See docs/PROPERTY_MANAGER_SCOPE_0333.md for validation and limits. Restart after installation.

Relevant forms (0.33.2): service requests hide and disable irrelevant fields, filter recipients/targets/roles/departments by the selected work, and explain empty choices before review. Related recruiting, IT, property transaction and tenant repair forms share the same dependency behavior. Accounting requests no longer carry stale legal targets. See docs/CONTEXT_FORMS_0332.md for validation and limits. Restart after installation.

HR hiring costs (0.33.1): an accepted hire uses 60 completed HR minutes with no outside recruitment fee. HR payroll and separate paid campaigns remain. Hiring screens, cash requirements and confirmation show the current fee and capacity; shared staff work remains finite. See docs/HR_HIRING_0331.md for validation and limits. Restart after installation.

Home-office leadership transfer (0.33.0): move an active manager/director into a Home Office Director or VP position from their employee page. Existing employment identity, leave, oversight and authority spending remain; future payroll moves to the office and the old position becomes vacant. Real executive priorities and bounded parent funding remain subject to scope and cash. See docs/HOME_OFFICE_PROMOTION_033.md for behavior, validation and limits. Restart after installation.

Repair all (0.32.2): selected-property bulk repair with a combined cost preview, full-batch funding and qualification checks, active/full-system exclusions and real saved work jobs. Individual repair behavior, finite internal crew hours, authority enforcement and financial reconciliation remain. See docs/REPAIR_ALL_0322.md for validation and limits. Restart after installation.

Manager leave queue (0.32.1): covered future vacation stays with its manager when they return before the start date. Only genuine exceptions interrupt time; the inbox and employee views show who will review the request, when, or why the player is needed. Explicit policies and actual leave capacity/payroll effects remain. See docs/MANAGER_LEAVE_0321.md for validation and limits. Restart after installation.

Manager and director defaults (0.32.0): hiring a manager delegates daily work, including staged customer collection and real legal follow-up. Director appointments add bounded growth authority; the managing-director shortcut retains one employee and previews the responsibility raise. Explicit overrides, cash reserves and parent contracts remain effective. See docs/LEADERSHIP_DEFAULTS_032.md for behavior, validation and limitations. Restart after installation.

Daily management defaults (0.31.0): available managers now handle daily routines without a separate setup step. Industry-sized default purchase limits, cumulative commitments, cash reserves and existing policies constrain actions. Manager questions go to the decision inbox; safe leave requests go to the manager, including next-day requests. Tenant repairs receive same-day review. Explicit opt-outs and employee identities are preserved. See docs/MANAGER_DEFAULTS_031.md for behavior, validation and limits. Restart after installation.

Parent director inheritance (0.30.0): subsidiaries default to their nearest parent business director, with local-manager priority, explicit overrides, shared workload/budgets, career tracking and compensation reviews for added duties. Business leadership pages provide an inheritance toggle. Saved authority scopes remain explicit. See docs/DIRECTOR_INHERITANCE_030.md for behavior, validation and limits. Restart after installation.

Internal department configuration (0.29.2): Home office now shows visible Add/configure, Edit department and Hire staff actions above the service queue. Editing loads saved staff, tools and coverage; company/role selectors load existing configurations and filter matching employees. See docs/DEPARTMENT_UI_0292.md for validation and limits. Restart after installation.

Property work condition context (0.29.1): booking work now shows all eight system conditions, ages, attention levels and active work, with live property selection and selectable system cards. Costs and simulation behavior are unchanged. See docs/PROPERTY_WORK_VALUES_0291.md for validation and limits. Restart after installation.

Manager-led routine operations (0.29.0): available local managers now perform daily work before directors. Managers can follow up overdue invoices, book cleaning/grounds care and renew existing service plans within their budgets. Directors retain strategic decisions and absence cover. Routine policies and separate manager/director authority controls are in Management overview. See docs/MANAGER_ROUTINES_029.md for behavior, validation and limits. Restart after installation.

Customer collections (0.28.0): overdue invoices now offer reminders, installments, contingency agency recovery and direct legal work before write-off. Eligible invoices use 1% default / 8% late-payment tuning. Existing defaults and promised dates survive. See docs/CUSTOMER_COLLECTIONS_028.md for simulation behavior, validation and limits. Restart after installation.

UI workflow update (0.27.0): visible team hiring and policy controls, leader-first management, queue-first home-office services, selected-property repair links, inline form errors, clearer cash labels and an active-campaign Home. Simulation behavior and saves are preserved. See docs/UI_WORKFLOWS_027.md for validation and limits. Restart after installation.

Specialist hiring correction (0.26.3): HVAC, electrical, plumbing and real-estate vacancies now accept their automatic license requirements. Guided offers display and enforce licenses before a vacancy exists. See docs/SPECIALIST_HIRING_0263.md. Restart and retry the vacancy or offer.

Leadership career tracking (0.26.2): director and executive appointments, changed scope/limits and removals now appear in employee career history. Current leadership duties are visible on employee pages, including existing saves. See docs/LEADERSHIP_HISTORY_0262.md for behavior and validation. Restart after installation.

Leadership promotion pay (0.26.1): director and executive appointments now show and apply responsibility raises through the original employer payroll. Existing directors receive an inbox pay review on the next simulated day. Repeat appointments do not stack raises. See docs/LEADERSHIP_PAY_0261.md for behavior, validation and limitations. Restart after installation.

Revenue streams and equipment kits (0.26.0): gas stations, engineering firms and factories can configure offerings and buy capability kits with real staff, inventory/material, equipment and cash constraints. Existing contracts and unconfigured operating models are preserved. See docs/REVENUE_KITS_026.md for behavior, validation and limitations. Restart after installation.

Whole-dollar interface (0.25.1): all monetary displays and entry fields use whole dollars; exact cents remain in saved finances and unchanged agreements. 38 tests plus browser QA passed. See docs/WHOLE_DOLLARS_0251.md. Restart after installation.

## Personal residence — 0.25.0

Designate a personally owned vacant home as the player’s residence from its property page or Personal finances. Move out or switch homes later. A residence earns no rent, while upkeep, repairs and loan payments continue. Restart to load the update. See [behavior and validation](docs/PERSONAL_RESIDENCE_025.md).

## Vermont counties — 0.24.0

The game is now set in Vermont with all 14 counties. County filters, business locations and geographic authority work across the state. Existing campaigns receive a recovery backup and migrate when opened after restarting. See [migration and validation](docs/VERMONT_COUNTIES_024.md).

## Funding balances — 0.23.1

Funding selectors and capital transfers now show account cash, refresh during play, and carry the selected accounts into decision reviews. Restart the game to load the update. See [validation and details](docs/FUNDING_BALANCES_0231.md).

# Multiple games — 0.23.0

Use **My games** in the sidebar to create, name, copy and switch between independent campaigns. Your existing progress stays saved, and the launcher resumes the last opened game. Restart after installing. See [behavior and validation](docs/MULTIPLE_GAMES_023.md).

# Property scale update — 0.22.0

Empty lots and specialized buildings at three scales; licensed trade repairs; owner repair time; in-house agent closing work; earned HR recruiting support. Restart the launcher after updating. See [the increment notes](docs/PROPERTY_SCALE_022.md) for behavior and limits.

## Employee management update 0.21.0

**All employees → Open an employee** now provides benefits, vacation and other time-off requests, coverage estimates, approval history and a named primary supervisor. Supervisors may work in any owned company, including the home office. Approved absences reduce real capacity; paid banks distinguish available and reserved days. New and migrated employee names are unique without numeric suffixes. See [behavior and limits](docs/EMPLOYEE_MANAGEMENT_021.md). Restart the launcher after updating; compatible campaigns are backed up before the one-time upgrade.

## Separate home-office company update 0.20.0

**Home Office → Create a separate home-office company** provides an optional company with its own funding, payroll, costs and financial report. Its summary separates cash, earned service charges and unpaid internal balances. Internal charges cancel in group results. Existing departments stay with their employers. See [behavior and validation](docs/HOME_OFFICE_COMPANY_020.md). Restart the launcher after updating.

## Delegated-limit shortcut update 0.19.2

Management approval cards and review popups now offer **Change delegated limits**, opening the affected business's editable authority form. Following the link does not approve the expense. See [details and validation](docs/DELEGATION_SHORTCUT_0192.md). Restart the launcher after updating.

## Blocker shortcuts update 0.19.1

Time-skip blockers now link to the approval that needs attention, and the advance dialog shows pending approvals before a long skip. Common action errors include shortcuts to funding, staffing, policies, repairs and other relevant controls. See [behavior and validation](docs/BLOCKER_LINKS_0191.md). Restart the launcher after updating.

## Unified decision inbox update 0.19.0

**Decision inbox** is now in the main navigation with a live attention count. It brings together pending approvals, offers, staffing issues, repairs, lease decisions, overdue payments and active project follow-ups across your businesses and properties. Review links select the affected record; handling an issue elsewhere updates the inbox. See [coverage and validation](docs/DECISION_INBOX_019.md). Restart the launcher after updating.

## Financial detail update 0.17.0

**Finances** now breaks balances down into cash by entity, named properties and their recorded/estimated values, equipment purchases and depreciation, and employee payroll costs and unpaid amounts. Current monthly pay structure is separate from actual expenses. See [details and validation](docs/FINANCIAL_DETAIL_017.md). Restart the launcher after updating; reports leave saved simulation state unchanged.

## Concurrent projects update 0.16.0

Engineering, construction, trades and factories can work on multiple contracts using shared qualified capacity. On each business page, set **Maximum concurrent projects** and **Planning window** under automatic jobs. The staffing guide now totals active work and each job has its own progress card. See [behavior and validation](docs/PARALLEL_PROJECTS_016.md). Restart the launcher; existing campaigns receive a recovery backup before updating.

## Developer testing tools update 0.15.0

Open **Management tools → Developer tools** to add, remove or set cash and change business conditions, inventory, property systems and employee ratings. Available in existing campaigns. Edits autosave, create a backup before the first change and label the campaign modified. See [controls and validation](docs/DEVELOPER_TOOLS_015.md). Restart the launcher after updating.

## Property service businesses update 0.14.0

Buy or start **cleaning, landscaping and security companies**, or purchase outside visits directly from **Property services**. Plans consume time, supplies and prepaid funds; owned crews share capacity with outside customers. Property care affects new rent offers, and completed patrols reduce incident risk. See [behavior and remaining scope](docs/PROPERTY_SERVICES_014.md). Restart the launcher after updating; supported campaigns receive a recovery backup before migration.

## Contracts and purchasing update 0.13.0

**Contracts & purchasing** adds legal transaction reviews, buyer-specific transfer consent, disclosed repair covenants and prepaid outside-service agreements with finite delivery capacity. The screen separates cash, reserved credit, actual expenses and negotiated future concessions. See [behavior and remaining scope](docs/COMMERCIAL_CONTRACTS_013.md). Restart the launcher to load the update; supported campaigns receive a recovery backup before migration.

## Service projects update 0.12.0

**Home office services** now offers targeted recruiting, candidate assessments, employee onboarding, succession shortlists, checkout deployment and inventory integration. **Property workbench** shows tenant repair requests and real repair responses. See [behavior and remaining scope](docs/SERVICE_PROJECTS_012.md). Restart the launcher to load the update; your campaign is backed up automatically before migration.

## Operations update 0.11.0

Open **Operations and recovery**, **Home office services**, and **Property workbench** from the links beneath the cash header. These add dated distress, optional authority and executive policies, actual service queues, company locations, property systems, tenant offers, conditional sales and funded flips. Close and reopen the game to load the update; supported older campaigns are backed up automatically on upgrade.

See [release behavior and limitations](docs/OPERATIONS_RELEASE_011.md) and [executed validation](docs/VALIDATION.md). The original project notes below remain preserved.

# Empire Manager 0.10.0

A local Python business and real-estate simulation. Version 0.5 adds skilled trades, construction, gas stations, grocery stores, banks and car dealerships with working operations, staffing guides and startup budgets.

## Play

Close any existing game window, then double-click **Play Empire Manager.cmd** in this folder. Your current campaign is resumed. The first 0.5 load adds the new opportunities to recognized older campaigns and creates a uniquely named pre-migration SQLite backup. Existing companies, people, properties and balances are preserved.

```powershell
cd C:\Projects\EconmicSimulationGame
.\.venv\Scripts\python.exe -m economic_simulation
```

The launcher uses this project's existing Python environment and Microsoft Edge WebView2. This remains a runnable source project, not a standalone installer.

## Business navigation (0.5.2)

Choose **Businesses**, then open a company. Its **Operations, Team, Properties, Finances, and Ownership** tabs keep the same management context. The header shows the company, ownership path and cash account. Employee and owned-property links automatically select the correct employer/owner, even from older bookmarks with a different account selected.

The **Manage** selector switches companies while keeping the relevant section; it clears stale employee/property IDs. Markets label it **Purchase account** and explicitly show whose money pays. Viewing a listed asset does not change its buyer.

Sidebar directories show all businesses, all employees and all owned properties. Property cards identify the owner and open in that owner's context. Buying and opening opportunities are grouped under **Grow your empire**, with less frequent controls under **Management tools**. Candidate browsing is collapsible; staffing and hiring remain linked from each team's page. No money is pooled or moved by navigating.

## Organization charts (0.5.1)

Open **Organization** for two graphical views:

- **Companies & real estate** connects the personal owner, holding company, subsidiaries and owned properties. Focus on any owned company to see its subtree. Gold property cards show the actual owner and any tenant or operating occupant; leasing does not change the ownership edge. Sold properties and companies outside your control are excluded.
- **Employee hierarchy** selects one business and follows its saved position reporting lines. Vacant supervisor positions retain their reports; joining employees show their start date. Open an employee card for details or use **Change reporting line** to update the supervisor through the existing management screen.

Use the shared **Manage** selector to choose the business or ownership root. Collapse individual branches, expand/collapse all, search names or roles, and zoom or fit the chart. Search opens ancestors of matching cards and restores the previous expansion state when cleared. Both charts scroll horizontally and vertically and are usable with keyboard controls. Business detail pages link directly to their employee and ownership charts. These views are read-only and need no save migration.

## New industries (0.5.0)

All six categories appear in **Buy a business** and **Empire tools → Business development**. Each supports separate ownership accounts, premises purchases and leases, acquisitions, startup staffing gates, hiring, payroll and financial reports.

- **Skilled trades:** plumbing/electrical jobs delivered by tradespeople and supervised apprentices. Fixed fees accrue as work is delivered; materials cost $35 per qualified work hour.
- **Construction:** builders and supervised laborers deliver larger fixed-fee projects. Materials cost $90 per qualified work hour. Both contracting industries automatically accept new jobs and collect completed invoices after 14 days.
- **Gas stations:** sell gallons of purchased fuel; overlapping cashiers and forecourt attendants determine capacity.
- **Grocery stores:** sell food baskets; cashiers and stockers must overlap. Perishable stock loses 1% daily (at least one unit when any stock remains).
- **Car dealerships:** hold individually costed vehicles and need overlapping salespeople and mechanics for sales and preparation. Inventory is expensed on sale.
- **Banks:** simulated outside customers create deposit liabilities and receive loan assets. Teller capacity limits deposits and service fees. Credit officers issue up to two $20,000 loans per weekday, preserving one month of base payroll plus a configurable 25–100% deposit cash reserve. Loan principal repays over 12 monthly installments, with 10% annual interest; deposits earn 2%. A 3% modeled first-installment default writes off the remaining balance. Pause new lending without interrupting existing repayments. These are simplified game rules; customer loans are separate from the player's borrowing facilities.

Trading uses the game's existing five-weekday calendar. Startup and acquisition costs vary substantially; banks and dealerships require more capital. The staffing guide uses the same capacity definitions as actual operations. Deposits, loan principal, unbilled work and inventory appear on the balance sheet rather than being counted as cash profit.

## Staffing and guided hiring (0.4.3)

Open an owned business to see its **Staffing guide** near the top of the page. It explains the workload, minimum roles required to open, weekly hour targets, active/incoming headcount, net shared assignments and an estimated five-weekday coverage picture. Targets are planning baselines, not guarantees; role purpose and assumptions are expandable. Engineering uses a visible 20-working-day project throughput goal, while rental businesses have no mandatory employee requirement.

Choose **Hire for this gap** to see the role requirements, eligible applicants, visible qualifications and demonstrated skills. Missing/expired required licenses and conflicting commitments are explained. Unknown skills remain unproven. Hours start at the suggested gap (4–40 hours); changing hours updates the suggested salary and minimum funding. Review shows the $300 immediate recruitment fee and estimated recurring wages, benefits and payroll tax. The game fills an existing vacancy or creates one atomically with the offer, then returns to the business staffing guide. New hires start in three days and are counted as incoming immediately.

Existing advanced vacancy/hiring controls remain in a collapsed section. When planned hours are covered but effective coverage is low, check shifts, leave, training and shared assignments before adding more employees. Optional specialists are separate from core staffing recommendations.

## Engineering jobs (0.4.2)

Engineering companies automatically accept another quoted job on the next staffed working day after completing the current one. Automatic acceptance is enabled for existing and new companies; disable it from **Automatic engineering jobs** on the company page to return to manual acceptance. Routine completion does not pause a time skip in automatic mode; other important events still can.

Job quotes vary in work size and fee per qualified hour. Accepted terms remain fixed. Required hours consume real qualified staff capacity alongside support and consulting work. The agreed fee is earned in proportion to progress, invoiced once on completion, and paid 14 days later. Payroll and other operating costs continue throughout the work, so fee and required effort affect profitability.

The project panel shows hourly contract value before costs, remaining work, fee earned, the latest day's work, a stable next-job quote, and recent project invoices with payment status. Existing saves keep current contract terms and progress. Invoice history begins with completions under this update.

## Business premises and rent (0.4.1)

Open a company and find **Operating premises and rent**. **Buy real estate with this company** selects its own cash account. After purchasing a vacant building in the same region (condition 40+), use **Use a building this company owns** to move in and stop external rent. Property upkeep continues.

If your property/holding company owns the building, use **Lease from another owner in your group** on the operating company's page. The selected owner receives the refundable deposit and daily rent. The tenant records rent expense and the owner records rent income; internal flows cancel in combined group results. Existing divided spaces remain managed through **Spaces & leases**. Whole-building use is a simplified game assignment; it does not model a zoning application.

Default external premises rent now reaches a named non-player landlord ledger. New unpaid rent is retained and settled when cash is available, including after relocation or expiry. The update preserves historical journal entries; past external payments are not replayed. No save schema change is required.

## New controls

Expand **Empire tools** in the left navigation. Scroll the sidebar to reach the lower entries.

- **Business development:** compare six startup budgets, fund openings, hire through People, expand equipment, investigate acquisitions, integrate companies and arrange whole-company sales.
- **Policies & benefits:** effective-dated inherited policies, detailed benefits and parent locks. Individual career, compensation, education and reporting controls are linked from employee pages.
- **Shared services:** agreements, reserved staff time, headquarters, recruitment and manager authority.
- **Spaces & leases:** configure owned vacant buildings, lease units to external or linked tenants, handle deposits and arrears, convert permitted uses and undertake personal renovations.
- **Loans & taxes:** borrowing, collateral, optional owner guarantees, repayments, one-time restructuring, fictional tax filing and qualified research.
- **Regions & community:** delayed published observations, civic projects and insurance.
- **Brands & franchises:** establish a proven retail/restaurant brand or join an external brand; grant, audit, renew and end agreements.
- **Decision inbox:** review recorded exceptions and available responses.
- **Scorecard:** separate wealth, profit, employees and morale, with monthly history.
- **Forecast:** compare three demand scenarios over 1–90 days without changing the live campaign.
- **Campaign settings:** optional succession, cash alerts, and separate Guided, Entrepreneur or Sandbox saves. Sandbox records stay labeled as modified.

Choose the ownership account at the top of the screen when managing property, loans or taxes. Business actions identify the company explicitly. Actions show a review before committing; rule failures leave the saved state unchanged.

## Saves and recovery

Saves live in `saves`. New campaigns create separate `campaign-*.sqlite3` files and update `last-campaign.txt`. To reopen an older campaign explicitly:

```powershell
.\.venv\Scripts\python.exe -m economic_simulation --save .\saves\campaign.sqlite3
```

The source update does not copy, overwrite or remove campaign saves. Older schemas 1 and 2 are recognized and backed up before upgrading to schema 3. Unknown versions are rejected. The active campaign has one writer and daily changes commit atomically with the journal.

## Validation and remaining work

See `docs/VALIDATION.md` for the regression and migration evidence, and `docs/FULL_GAME_STATUS.md` for remaining work. This is a substantial playable expansion, not a claim that every requirement in the comprehensive handoff is finished. Large-workforce performance, decades of campaign balance, all exploit/acceptance cases, advanced search and pagination, and standalone Windows packaging still need work.

All prices, interest, employment policies and taxes are fictional game rules, not current real-world data.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The original comprehensive handoff and `docs/DESIGN_DECISIONS.md` remain the design authority. `docs/README_v03.md` is historical documentation for the earlier build.

## Property categories (0.6.0)

The property market and portfolios filter residential, commercial and industrial buildings by district. Commercial shops and offices support most businesses; trades and construction use industrial workshops and warehouses. Any controlled company can own rental investments in any category. Space conversion supports all three uses. Existing campaigns receive new listings with a pre-upgrade save backup; existing ownership and leases are retained. Restart the launcher after installing.

## Factories and boutiques (0.6.1)

Factories fulfill manufacturing orders automatically with machine operators, supporting production workers and material costs. They use industrial premises. Boutiques sell clothing and accessories from inventory, requiring overlapping sales and stock staff and commercial premises. Both can be acquired or started, with staffing guidance and organization charts. Existing saves upgrade once with a backup and preserve prior assets and balances.

## Self-storage (0.6.2)

Buy or start a self-storage facility. Finite fitted-out units earn rent only when occupied, including weekends. Staff handle new tenants; regional demand and monthly departures affect occupancy. Uncovered maintenance is outsourced. Startups begin empty. Facilities use industrial premises. Existing saves gain the new opportunity with a pre-upgrade backup.

## Always-visible cash (0.6.3)

The sticky header displays cash on hand for the selected account on every page, including while scrolling. Balances refresh during time advances and while idle. Decision and time-advance dialogs also display the account balance.

## Owned-bank financing (0.6.4)

Choose an operating bank you own as lender in Financing. Owner loans receive a 2-point APR discount (1% floor) and higher equity/collateral approval limits. The bank must fund the loan above its cash reserve; repayments, interest and restructuring fees reach its ledger. Related balances and interest cancel in consolidated reports. Existing loans retain their terms.

## Rearrange ownership (0.6.5)

Use Organization → Companies & real estate → Rearrange business ownership. Select a business and its new owner. Choose Personal portfolio to remove a subsidiary from its parent while keeping it. Transfers retain staff, assets, subsidiaries, debt, leases and guarantees. Carrying-value investments and goodwill transfer through reorganization equity without cash, revenue or expense. Cycles and changes affecting pending sales are rejected. Inherited policies follow the new ownership path.

## Logistics and combined ownership benefits (0.7.0)

Logistics companies can be bought or started. Drivers, dispatchers and trucks provide finite delivery capacity. Related companies under a corporate parent or holding company automatically receive transport at allocated payroll, premises, overhead and fuel cost when cheaper than an outside carrier. Other personal holdings do not automatically share transport: use Rearrange ownership to form a group. Outside freight costs $300 per delivery; retailers and material-based project businesses now incur delivery costs based on volume. Cross-region group loads use twice the capacity and cost. Group work takes priority, then outside customers use the remaining capacity. Bank financing and transport benefits work together; duplicate providers share demand rather than multiply discounts. Costs, internal reimbursements, savings and capacity are visible on business pages.

## Time-skip interruption controls (0.9.0)

Under Campaign settings → Time-skip interruptions, set a minimum financial event amount (for example $1,000). Smaller losses, missed payments and funding shortfalls remain recorded but do not pause a skip. Exactly the threshold pauses; zero preserves all financial pauses. The routine-completion switch controls renovations, acquisitions, completed jobs, training and similar notifications. Safety, staffing, lease expirations, collateral covenants and the separate low-cash alert still pause. No debts are forgiven and no decisions are automatically accepted. Preferences apply to future skips and are shown in the Advance time dialog.

### Optional holding company

New campaigns start with only the personal portfolio. Create and name a holding company from Personal finances or Open and develop businesses when needed; it starts empty and funding is a separate action. Unused default companies are omitted from existing saves’ selectors and charts. Previously used company accounts, assets, subsidiaries, obligations, and history remain available. Operating businesses can still be started through the existing business formation screen.

### Annual pay reviews and employee leadership

Employees expect a 3% annual raise by default, configurable from 1–20% in business leadership controls. The first review is a year after employment or acquisition, whichever is later; completed reviews restart the yearly clock. Overdue reviews reduce morale and can affect retention. Raises change future base pay and hourly rates, never past payroll.

Enable manager authority on a business page to delegate recruitment into existing vacancies, stock purchases, automatic jobs, training, credential renewals, rental preparation and listings, annual staff raises and funded routine interventions. Limits and availability are checked; leaders cannot approve their own raises.

Appoint an existing employee as director on one or several business pages. Their employer and salary do not change. Each business reserves one working hour daily, with up to five assignments and capacity checks; shared-service assignments must be ended first. The director limit covers both each decision and total daily commitments across assigned businesses. Hiring uses annual base salary plus recruitment fees; raises use the annual incremental base salary. Other expenses use the transaction amount. Stock orders above authority are escalated whole. Above-limit or unaffordable requests go to the business page and decision inbox for owner approval. Acquisitions, sales, ownership transfers and new borrowing remain owner decisions.

### Management overview

The sidebar Management overview page lists managers and employee directors, their employer and assigned businesses, current availability, and the policies followed in each business. Search by person or business. Edit authority, annual raises, assignments and operating policies without switching businesses; directors can apply hiring and equipment-growth modes to all their assigned businesses while preserving local budgets and targets.

Hiring can freeze, fill existing vacancies, fill vacancies up to a target, or create a selected role until the target is reached. Weekly decisions count both active and incoming employees and remain subject to leader authority and funding. Equipment growth defaults off. Sales businesses can propose or automatically fund 21-day equipment upgrades toward a capacity target, requiring positive prior-30-day profit, sufficient monthly growth budget, retained cash and payroll reserve, and an available leader. Equipment automation supports retail, restaurants, gas stations, groceries, boutiques and dealerships; other industries can grow through hiring targets. Existing expansion commitments count against the monthly equipment budget. Jobs, inventory orders, training and rental preparation have separate switches. Policies and authority settings preserve each other.

### Specialist value and shared professional services

Shared services now explains each specialist role, its qualified work delivered, dated service-hour balance, local base-pay commitment, shared-service charges and realized operating savings. Local and shared employees use the same work buckets: hours allocated elsewhere are removed from the employer before benefits are calculated. Benefits are capped rather than endlessly stacking.

HR improves covered staff morale and loyalty; each 60 banked minutes reduces one recruitment fee from $300 to $150. IT provides up to 10% productive capacity from the same operating hours. Purchasing reduces actual supplier/admin overhead by up to 20%, plus up to 5% supplier rebates on goods sold or project materials consumed. Unsold inventory retains its standard unit basis; sales rebates reduce cost of sales when earned. Marketing increases demand by up to 15% in sales and freight operations; production, staff and stock remain constraints. Logistics coordination reduces outside freight quotes and carrier fuel costs by up to 20%, with finite carrier capacity and at-cost group freight preserved.

Accounting uses two banked qualified hours to prepare a dated 30-day report covering revenue, expenses, margin, cash, receivables, payroll, inventory and cash divided by average daily expense. Basic financial information is always available. Legal uses 20 banked qualified hours to negotiate up to 5% off an available acquisition, capped at $25,000 and its remaining goodwill; negotiation is once per listing and never commits the purchase. Accounting and legal service work requires valid professional licenses. HR, legal and accounting service balances expire after 30 days and cap at 80 qualified hours per role per recipient. Salaries remain payable even when service capacity is unused; choose local hires or shared hours based on the workload.


## Design extension, increment 1 (0.10.0)

Management overview now has cash commitment forecasts, saved authority contracts, organizational/geographic scope, parent delegation, transaction/project/monthly limits, headcount and compensation bands, objectives and an employee decision audit. Contracts cover existing purchasing, hiring, raises, training, maintenance, leasing, growth and project acceptance. Required approvals and cash guardrails cannot be suppressed by financial notification thresholds. A pending approval blocks a new long skip; one-day recovery remains available.

Existing campaigns retain their existing delegation settings. Open Management, expand a business's cash commitments and authority contract, review the forecast, and save limits to activate the stronger controls. No headquarters or holding company is required.

This is the first design increment, not completion of the larger design. See docs/DESIGN_UPGRADE_PLAN.md for the code inventory, acceptance gates and remaining work.

## Automatic GitHub updates

Push to main to run the complete test suite and publish a numbered Docker build. Unraid can pull successful builds every five minutes. The build badge appears under the game logo and on the login page. See [GitHub and Unraid setup](docs/GITHUB_UPDATES_035.md) for the one-time package visibility setting and installation.
