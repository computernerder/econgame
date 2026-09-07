# Customer collections — 0.28.0

## Implemented behavior

- New unsettled invoices in construction, trades, factories, cleaning, landscaping and security now have a seeded 1% default chance and 8% chance of a 30-day payment delay, replacing 5% default / 10% late. Other industries retain their existing payment models. An already recorded default or promised due date is preserved.
- Late customers retry payment automatically on the promised date. The player may request earlier recovery. Defaulted balances require recovery or an explicit write-off.
- Free reminder: customer response after three calendar days. Success collects the outstanding balance. Success chance is 85% for late customers and 25% for recorded defaults.
- Free installment proposal: response after three days; accepted proposals pay three installments ten days apart. Acceptance is 90% for late customers and 60% for defaults. Defaulted customers have a seeded 15% missed-payment chance for each installment. Prior receipts survive a broken plan.
- Contingency agency: response after fourteen days; success chance is 95% for late customers and 65% for defaults. Success collects the balance, deducting a 25% fee. Failed collections charge nothing. Gross receipts, fees and net cash are separate journal amounts.
- Direct legal collection: use outside counsel ($1,800 prepaid for 20 hours) or an owned configured legal department with real qualified employee capacity and allocated payroll costs. Existing skill-based outcomes can fail or recover only part of the balance. Defaults are eligible even if their saved scheduled due date is in the future.
- Only one recovery may be active for an invoice. Each reminder, plan and agency option is attempted once; legal allows one completed attempt. Stable invoice-based outcomes prevent rerolling through repeated clicks or saves. Write-off is blocked during active recovery. Cancel unfinished legal work through Home office if required.
- All receipts reduce existing receivables rather than earning revenue again. Only remaining balances become bad-debt expense when explicitly written off. Closed businesses use the same collection pipeline.
- Customer collections appears near the top of Operations and recovery. The decision inbox opens the specific invoice and its recovery choices. Business and financial-detail invoice links lead to collections. Active recovery temporarily clears the decision and shows its next date. Failure or partial legal recovery restores the decision and raises a financial event, subject to existing skip thresholds.
- Recovery requests, actual receipts, fees, losses and remaining balances are saved. History shows the latest 100 records; open invoice details retain their recovery history. Existing journals are preserved. Prior write-offs are not undone and historical recovery details are not invented.

## Validation actually executed

- First targeted run: 58 passed (collections, UI workflows and completion systems).
- Full suite: 524 passed and one failure in the engineering invoice journal test. Its expected historical memo was restored in the implementation; the test was preserved.
- Final focused run: 46 passed, including that previously failing test, all collection tests, UI workflow tests and decision-inbox tests. Three additional cases cover pending-card visibility, wrong-account legal requests and partial legal outcomes. Two existing dependency deprecation warnings remain. The full suite was not repeated after these focused corrections.
- Tests cover fixed risk boundaries, legacy late/default records, dated receipts, odd-cent installment reconciliation, failure, one-attempt rules, competing commands, no double income, write-off after partial recovery, legal fees, seeded save/load, command idempotence, daily/batched stepping, closure and exact invoice navigation.
- Browser walkthrough used a SQLite backup of the current campaign at 2026-03-19. That snapshot contained no open overdue invoice decisions, so two clearly labeled QA invoices were added only to the backup. Verified inbox navigation, comparison of choices, contingency fee and date preview, confirmation, no immediate cash change, saved status and the response date after server restart. No live campaign was advanced or edited.
- Python source parses successfully. Installation checks original source hashes and tested file hashes, backs up changed source, and verifies installed hashes. Saves are excluded from installation.

## Limits and next step

These are fictional game tuning values, not real collection statistics. Reminders and installment administration currently abstract routine administrative time. New payment-risk tuning applies to the industries already modeled with customer credit risk; engineering and retail were not converted to a different credit model. There is no recurring customer credit profile, negotiated settlement percentage, deposit/credit policy, automatic manager collection policy or post-write-off recovery yet. A useful next extension is customer-level credit terms and delegated follow-up within approved collection budgets.
