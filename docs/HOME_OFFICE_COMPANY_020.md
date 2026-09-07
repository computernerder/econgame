# Separate home-office company — 0.20.0

Home Office now exposes the existing independent office-company formation path directly. The player chooses a company name, funding owner, region and working reserve. Default funding is $102,000: a $10,000 deposit, $25,000 fit-out asset, $7,000 setup expense and $60,000 cash reserve. Formation uses the normal reviewed and validated startup command, takes at least 28 days and requires a manager before opening. It creates a separate ownership record and company ledger; capital is an investment by its owner, not service revenue.

Dedicated office companies appear above the work queue with their own cash, unpaid payroll, internal receivables/payables, and recorded last-30-day results. Results separate earned internal service charges, wages/benefits/payroll tax, other costs and company profit. Links lead to the company financial report, capital contribution form, employee directory and department setup. When available, a dedicated office is selected as the default employer in department setup; an explicitly selected office takes precedence.

This extends the existing financial model rather than creating a second wallet or department-only shadow accounts. The provider employs and pays its staff. Department tools are charged to it. Qualified work consumes shared labor capacity and records matched internal service charges and balances. The existing daily settlement transfers only available debtor cash. Group results eliminate reciprocal internal charges and balances; office payroll, tools, premises and unused capacity remain real costs. An office in development cannot deliver department work before opening. Its operating picture now reports actual delivered staff minutes and outstanding queued effort instead of a generic closed-business message.

The feature is optional. Existing departments, people, properties, ownership and balances are not automatically moved. A small business may continue using its own employees or outside specialists. Existing office companies automatically appear, with no schema migration. Employees remain normal persistent employees and executive appointments use the existing management system.

Known limits:

- This release does not provide a one-click migration of an existing department and its employees between legal employers.
- Charges allocate the existing modeled delivered labor cost. Office overhead and unused labor are retained by the provider, not automatically spread across recipients.
- Internal balances may also contain rent, transport or other modeled internal transactions; they are labeled as balances rather than service-only invoices.
- The financial summary uses recorded daily income and expense entries for the last 30 days. Full account and payroll detail remains in Finances. Department capacity refers to the latest recorded daily capacity, not a promise of future availability.
- Forming the company supplies neither employees nor completed services for free. Leadership, tools, coverage and expertise still require configuration.

Validation performed:

- Five dedicated tests cover optional formation, actual funding/account separation, failed formation rollback, preserved existing departments, provider defaults, report links, read-only views, real service labor and receivables, cash settlement, consolidation, save/load reconciliation, opening constraints and unused-capacity costs.
- Full regression: 372 passed in 178.57 seconds.
- Targeted service, operations and formation regression: 60 passed, with two existing dependency deprecation warnings.
- Browser QA in an isolated campaign copy: reviewed and formed an office through Home Office, checked the $60,000 office reserve and $7,000 startup loss, and inspected separate finance and department navigation. The actual campaign is excluded from source installation.

Next: a reviewed department/employment transfer workflow could make it easier to move an existing shared-service operation into the dedicated company while preserving contracts and outstanding work.
