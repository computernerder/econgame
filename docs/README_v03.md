# Empire Manager

A local Python business and real-estate simulation. Version 0.3 adds business acquisitions, distinct revenue models and named employees alongside the existing buy, improve, flip and rent property path.

## Play

Double-click **Play Empire Manager.cmd** in this folder. It starts the desktop game using the project's Python environment.

Or run from PowerShell:

```powershell
cd C:\Projects\EconmicSimulationGame
.\.venv\Scripts\python.exe -m economic_simulation
```

The desktop uses Microsoft Edge WebView2. Startup errors appear in a message and are recorded in `saves/startup.log`. The existing Python environment was created with Codex's bundled Python 3.12.14; it depends on that interpreter remaining available. This is a runnable source project, not a standalone installer.

## Your first few minutes

1. Start with $350,000 in your personal account and browse **Property market**.
2. Open a listing to compare its condition, value, potential rent and holding costs.
3. Buy a property. Closing fees and the remaining cash are shown before confirmation.
4. Purchase a renovation, find a tenant, or arrange a sale. Work, tenant search and selling take time.
5. Use **Advance time**. The game pauses when work completes, a tenant moves in, a sale closes or a lease ends.
6. Review **Finances** for actual income, expenses, profit, cash and expandable journal entries.

You can keep everything personally owned. To hold properties in a company, transfer capital from **Personal owner**, then select **Your property company** in the account selector. The two accounts stay separate. Returning invested capital is supported; acquired companies can distribute earned profit to their direct owner from their management screen.

## Buying and developing businesses

Open **Buy a business** and inspect a listing. Six initial opportunities cover retail, restaurants, engineering, property management and rental ownership, including a larger grocer with its own premises and an apartment. Review the included cash, inventory, equipment, staff, property and operating commitments before committing the price plus a 1% fee. Closing takes three days and pauses time.

Use **My businesses** to inspect revenue by source, staffing constraints, inventory, invoices and payroll. Retail needs stock and checkout coverage; restaurants need cooks and servers together; engineering splits qualified hours across retainers, consulting and fixed-fee projects. Property managers earn external management and maintenance fees. Rental businesses collect rent from their actual leases.

Select a business account to buy property or another business. Subsidiaries keep their own finances and employees. **Finances → Include owned companies** consolidates operations and eliminates internal dividends and ownership stakes.

Use **People** or a company's team table to adjust pay and shifts, book training, approve paid leave or end employment. Create vacancies and make offers from the company screen. Hiring costs $300 and starts after three days. Payroll accrues daily and settles Fridays; benefits and overtime add costs. Morale, engagement, burnout, qualifications and demonstrated skills affect available work. Unknown skills stay unproven until relevant work or training demonstrates them. **Organization** shows direct owners and reporting positions.

## Saving and recovery

Every successful command and completed day saves automatically to `saves/campaign.sqlite3`. Closing and reopening resumes this campaign. Real time outside the game does not advance it.

Skips longer than seven days first update `saves/campaign.checkpoint.sqlite3`. **Finances → Create backup** updates `saves/campaign.manual-backup.sqlite3`. These are rolling backups, so copy one to a different filename if you want to retain a particular point permanently.

To open a backup or separate campaign without overwriting your main save, close the game and run:

```powershell
.\.venv\Scripts\python.exe -m economic_simulation --save saves\another-campaign.sqlite3
```

An absent filename starts a new campaign; an existing compatible file resumes it. To restore a backup, copy it to a new filename and open that copy with `--save`. Version 0.3 automatically upgrades recognized version-1 saves, preserving their properties, cash and journal. It first creates a uniquely named `campaign.before-v2-*.sqlite3` backup. Close all old game windows before upgrading. Unknown versions are rejected. Future compatibility still requires explicit migrations.

## Development

With Python 3.11 or newer available:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pytest -q
```

For browser development, use the same UI and engine:

```powershell
.\.venv\Scripts\python.exe -m economic_simulation --browser --save saves\development.sqlite3
```

Open the printed local launch URL. Each launch has its own session token. The server binds only to loopback. No CDN, account, online asset, telemetry or paid API is required for gameplay. Dependency installation requires internet access.

## Code layout

- `economic_simulation/domain.py`: pure models, commands, quotes, calendar rules and double-entry posting proposals.
- `economic_simulation/business_models.py`, `business_rules.py`, `business_views.py`: business ownership, employee identities, industry operations and reporting.
- `economic_simulation/application.py`: single writer, read models, command validation and cancellable time advancement.
- `economic_simulation/persistence.py`: SQLite snapshot, journal, events, idempotency and backups.
- `economic_simulation/web.py`: local authenticated commands and server-rendered screens.
- `economic_simulation/desktop.py`: Windows window, local server lifecycle and campaign process lock.
- `economic_simulation/content/`: scenario and property data in integer cents.
- `economic_simulation/templates/` and `static/`: local interface and original vector illustrations.
- `tests/`: economic, persistence, calendar, concurrency and HTTP regression checks.
- `docs/DESIGN_DECISIONS.md`: accepted direction and implementation choices.
- `docs/VALIDATION.md`: executed checks, results and remaining limitations.

The original `models.py` starter remains as a historical, unused demo model; the playable game uses `domain.py`.

## What is still ahead

Starting or selling whole businesses, richer employee ambitions and culture, resignations and retirement, configurable reporting lines, financing, income taxes, detailed regional economics, personal renovation work and optional succession. The full handoff document is preserved in the project.

Current property economics are deliberately forgiving. Values are fixed except for improvements; buyers and tenants do not default; renovations have known costs and dates. An occupied property must finish its lease before sale or renovation. Multi-unit properties currently use one aggregate lease. Daily cash settlement and capitalization of all purchased improvements are first-version simplifications. Wealth estimates and realized profit are displayed separately.

Business tuning is provisional. Shops and service businesses open on weekdays. Staff schedules use Monday–Friday with editable hours and starting times; this version allows up to 100 positions per company. Client contracts and supplier prices are fixed, customers pay on time, and equipment depreciation is not modeled. Culture currently uses team morale as a clearly labeled early proxy. Owned operating premises remain in use and cannot yet be repurposed or sold. Property management client counts expand through acquiring more companies; external contracts are not individually editable yet.
