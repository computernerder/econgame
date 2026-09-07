# Whole-dollar interface — 0.25.1

Installed behavior: monetary counters, balances, reports, funding selectors, review dialogs, notices and monetary inputs display nearest whole dollars. Half dollars round away from zero. Percentages, work hours and the underlying integer-cent ledger retain their precision. Fractional per-minute service rates are described with their equivalent whole-dollar hourly rates.

Existing monetary form defaults keep their original amount when submitted unchanged; explicitly edited inputs use whole dollars. Existing event history is formatted when displayed, without rewriting saves. API numeric financial fields remain integer cents; human-readable response strings use whole dollars.

Validation executed: 35 tests across test_game, test_campaign_product, test_funding_balances and test_home_office_company; 3 new test_money_display tests covering rounding, JSON precision, all campaign screens, standard pages, monetary inputs and read-only financial state. All 38 passed (two existing dependency deprecation warnings). Node syntax check passed. Browser QA confirmed no fractional currency on the employee page, unchanged salary retained 345678 cents behind a displayed $3,457, and editing the salary to $3,460 persisted 346000 cents in an isolated QA save.

Limits: displayed totals and rounded line items may differ by a dollar because reconciliation uses exact cents. No save migration or simulation-rule change is required. Restart the game to load the new server templates and scripts. Next step: continue the existing simulation backlog; this increment is limited to monetary presentation.
