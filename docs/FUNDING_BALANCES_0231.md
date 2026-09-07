# Funding balances — 0.23.1

Account selectors now show each controlled account’s actual ledger cash. Funding forms show the selected account and cash alongside the field. This covers company formation, expansion, service work, property funding, financing and the purchase-account selector. Personal/holding-company contributions, subsidiary funding and profit distribution show the fixed source account’s cash beside the amount entry.

Balances refresh through the existing progress poll and update immediately when the selection changes. Review dialogs show the form’s selected accounts when present, including an owner funding a subsidiary while viewing the subsidiary. Cash is not combined across accounts. Tooltips explain that reserved project assets and unused credit are excluded and existing obligations and approval limits still apply. No simulation actions, financial limits or saved-game schema changed.

Validation: 30 tests passed: test_campaign_product.py, test_home_office_company.py, test_saved_games.py (27), and test_funding_balances.py (3). Both JavaScript files passed node --check. Browser QA on an isolated campaign copy verified the home-office funding dropdown, changing from Personal portfolio to Northbank Engineering, and the review showing Northbank’s balance while the page remains on Personal portfolio. No company formation was confirmed. Two existing dependency deprecation warnings remain.

Limit: cash on hand is not a forecast of discretionary cash after future liabilities; existing server reviews still enforce affordability and reserves. No additional simulation work is introduced by this display update.

Restart the game server/launcher to load 0.23.1. The installer backs up changed source and does not modify campaign saves.
