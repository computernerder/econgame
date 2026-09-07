# Developer tools — 0.15.0

Open **Management tools → Developer tools → Enable developer tools**. This works in existing entrepreneur, guided and sandbox campaigns. Restart the game launcher after installation.

Available testing controls:

- Add, remove or set cash in a selected personal, holding-company or owned-business account; dollar inputs accept cents. Negative balances are rejected.
- Set base daily demand, operating capacity, reputation, workplace culture, equipment condition and customer relationships for owned businesses.
- Set purchased inventory quantities. Added lots arrive on the current simulation date; removals consume oldest lots first. Inventory balances reconcile at the existing unit cost.
- Set one property system or all systems to a chosen condition. The saved aggregate condition is synchronized so the next daily step does not apply the change twice.
- Edit an employed person's existing skills, morale, engagement, burnout, loyalty and trust while preserving their identity and employment contract.

Cash and stock edits use `equity:developer`, not operating income or expense. Normal sales and later stock consumption still generate their normal revenue and costs. All controls use the existing preview, revision checks, one-writer command pipeline and duplicate-command protection. Developer tools do not bypass local-session authentication.

The first applied edit creates `<campaign>.before-developer-edit.sqlite3` alongside the save. Opening the menu, previewing, or enabling controls does not create this backup or mark an otherwise unmodified campaign. An applied edit marks the campaign modified permanently, including when controls are subsequently disabled. Each edit records command ID, simulation date, target, field, before and after values in `systems.developer_history` and Activity. The UI shows the most recent 100 edits. Existing campaigns require no new schema migration for these optional records.

Scope and limits: this is a bounded scenario editor. It does not edit ownership, debts, contracts, licenses, qualification credentials, date, bank deposit balances or arbitrary saved JSON. It does not reopen closed businesses or reverse campaign insolvency. Demand parameters remain subject to each industry's existing operating model. Use normal game commands and normal time advancement for those workflows; more testing controls can be added as explicit validated commands.

Validation actually executed:

- `python -B -m pytest -q tests/test_developer.py`: 14 passed.
- `python -B -m pytest -q`: 295 passed in 152.44 seconds, with two existing dependency deprecation warnings.
- Browser test on an isolated copy of the current campaign: enabled tools, previewed and applied $1,000,000, verified header balance changed from $65,319.05 to $1,065,319.05, modified label and persisted audit. Expanded cash form visually inspected.
- Tests cover disabled controls, valid dollar conversion, invalid input rollback, owned scopes, ledger reconciliation, unchanged current profit, stock lots, preview isolation, backup creation, duplicate submission, stable employee contracts, property repair consequences and reload persistence.

Installation excludes campaign saves and creates a source archive before copying reviewed release files. Existing source comments and historical design documentation are retained.
